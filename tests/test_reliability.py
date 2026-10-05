"""Behavioral regressions for completion, retries, context and real CLI orchestration."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.backends.base import BackendResult
from harness.backends.generic import GenericCommandBackend, diagnostic
from harness.executor import StepExecutor
from harness.git_manager import GitManager
from harness.manifest import update_project_manifest
from harness.prompt_builder import PromptBuilder
from harness.state import write_json


@pytest.fixture
def project(tmp_path):
    phase = tmp_path / 'phases/0-test'
    phase.mkdir(parents=True)
    write_json(phase / 'index.json', {
        'project': 'test', 'phase': 'test',
        'steps': [{'step': 0, 'name': 'feature', 'status': 'pending'}],
    })
    write_json(tmp_path / 'phases/index.json', {'phases': [{'dir': '0-test', 'status': 'pending'}]})
    (phase / 'step0.md').write_text('Implement feature; verify the observable behavior.')
    for args in [('init', '-q'), ('config', 'user.email', 'test@example.test'),
                 ('config', 'user.name', 'Test'), ('add', '-A'), ('commit', '-qm', 'initial')]:
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def read_index(root):
    return json.loads((root / 'phases/0-test/index.json').read_text())


def save_index(root, data):
    write_json(root / 'phases/0-test/index.json', data)


def complete(root, **updates):
    index = read_index(root)
    index['steps'][0].update(status='completed', summary='Implemented feature',
                             verification={'status': 'passed', 'details': 'mock observable behavior checked'})
    index['steps'][0].update(updates)
    save_index(root, index)


def executor(root, invoke, **kwargs):
    ex = StepExecutor(root, '0-test', **kwargs)
    backend = MagicMock()
    backend.name = 'mock'
    backend.instruction_mode = 'native'
    backend.guardrail_files = []
    backend.invoke.side_effect = invoke
    ex._backend = backend
    return ex


def ok():
    return BackendResult('mock', [], 0, 'done', '')


def test_failed_backend_cannot_complete_or_commit(project):
    def invoke(*args, **kwargs):
        complete(project)
        return BackendResult('mock', [], 1, '', 'authentication failed', 'configuration')
    ex = executor(project, invoke)
    head = ex._git.checked('rev-parse', 'HEAD').stdout
    with pytest.raises(RuntimeError, match='Backend exited 1'):
        ex.run()
    index = read_index(project)
    assert index['steps'][0]['status'] == 'error'
    assert index['steps'][0]['next_action']
    assert 'completed_at' not in index
    assert ex._git.checked('rev-parse', 'HEAD').stdout == head
    assert ex._backend.invoke.call_count == 1


def test_no_progress_stops_without_three_identical_calls(project):
    ex = executor(project, lambda *a, **k: BackendResult('mock', [], 1, '', 'same failure'))
    with pytest.raises(RuntimeError, match='same failure'):
        ex.run()
    assert ex._backend.invoke.call_count == 1


def test_source_progress_allows_targeted_retry(project):
    calls = []
    def invoke(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            (project / 'feature.py').write_text('value = 1\n')
            return BackendResult('mock', [], 1, '', 'specific failure')
        complete(project)
        return ok()
    ex = executor(project, invoke)
    ex.run()
    assert len(calls) == 2
    assert 'specific failure' in calls[1]
    assert ex._git.checked('status', '--porcelain').stdout == ''


def test_transient_failures_are_bounded(project, monkeypatch):
    monkeypatch.setattr('harness.executor.time.sleep', lambda _: None)
    ex = executor(project, lambda *a, **k: BackendResult('mock', [], 1, '', '429 rate limit', 'transient'))
    ex._max_attempts = 2
    with pytest.raises(RuntimeError, match='rate limit'):
        ex.run()
    assert ex._backend.invoke.call_count == 2


@pytest.mark.parametrize('verification', [{}, {'status': 'passed'}, {'status': 'failed', 'details': 'failed'}])
def test_completion_requires_evidence(project, verification):
    def invoke(*a, **k):
        complete(project, verification=verification)
        return ok()
    with pytest.raises(RuntimeError, match='verification'):
        executor(project, invoke).run()
    assert read_index(project)['steps'][0]['status'] == 'error'


def test_remaining_blocked_step_prevents_finalization(project):
    def invoke(*a, **k):
        complete(project)
        index = read_index(project)
        index['steps'].append({'step': 1, 'name': 'blocked', 'status': 'blocked', 'blocked_reason': 'external dependency'})
        save_index(project, index)
        return ok()
    ex = executor(project, invoke)
    with pytest.raises(SystemExit):
        ex.run()
    assert 'completed_at' not in read_index(project)
    assert not (project / 'phases/baselines/0-test.json').exists()
    with pytest.raises(RuntimeError, match='unfinished'):
        ex._finalize()


def test_agent_cannot_skip_other_steps(project):
    index = read_index(project)
    index['steps'].append({'step': 1, 'name': 'second', 'status': 'pending'})
    save_index(project, index)
    def invoke(*a, **k):
        complete(project)
        index = read_index(project)
        index['steps'][1]['status'] = 'completed'
        save_index(project, index)
        return ok()
    with pytest.raises(RuntimeError, match='another step'):
        executor(project, invoke, auto_commit=False).run()
    assert read_index(project)['steps'][1]['status'] == 'pending'


def test_checks_execute_and_cannot_be_weakened(project):
    index = read_index(project)
    index['steps'][0]['checks'] = [[sys.executable, '-c', 'raise SystemExit(1)']]
    save_index(project, index)
    def invoke(*a, **k):
        complete(project, checks=[])
        return ok()
    with pytest.raises(RuntimeError, match='checks changed'):
        executor(project, invoke, auto_commit=False).run()
    assert read_index(project)['steps'][0]['checks'] == index['steps'][0]['checks']


@pytest.mark.parametrize('exit_code', [0, 1])
def test_independent_check_controls_completion(project, exit_code):
    index = read_index(project)
    index['steps'][0]['checks'] = [[sys.executable, '-c', f'print("check result"); raise SystemExit({exit_code})']]
    save_index(project, index)
    def invoke(*a, **k):
        complete(project, verification={})
        return ok()
    ex = executor(project, invoke, auto_commit=False)
    if exit_code:
        with pytest.raises(RuntimeError, match='Check failed'):
            ex.run()
    else:
        ex.run()
    step = read_index(project)['steps'][0]
    assert step['status'] == ('error' if exit_code else 'completed')
    assert step['verification']['source'] == 'executor'
    assert step['verification']['checks'][0]['exit_code'] == exit_code


def test_dirty_tree_is_protected_before_backend_call(project):
    (project / 'user-change.txt').write_text('keep me')
    ex = executor(project, lambda *a, **k: ok())
    branch = ex._git.current_branch()
    with pytest.raises(RuntimeError, match='existing changes'):
        ex.run()
    assert ex._backend.invoke.call_count == 0
    assert ex._git.current_branch() == branch
    assert (project / 'user-change.txt').read_text() == 'keep me'


def test_failed_step_resumes_with_no_commit_preserving_user_changes(project):
    ex = executor(project, lambda *a, **k: BackendResult('mock', [], 1, '', 'failure'))
    with pytest.raises(RuntimeError):
        ex.run()
    head = ex._git.checked('rev-parse', 'HEAD').stdout
    (project / 'user-change.txt').write_text('keep me')
    index = read_index(project)
    index['steps'][0]['status'] = 'pending'
    save_index(project, index)
    def invoke(*a, **k):
        complete(project)
        return ok()
    executor(project, invoke, auto_commit=False).run()
    assert read_index(project)['steps'][0]['status'] == 'completed'
    assert ex._git.checked('rev-parse', 'HEAD').stdout == head
    assert (project / 'user-change.txt').read_text() == 'keep me'


def test_commit_failure_propagates(project, monkeypatch):
    manager = GitManager(str(project))
    original = manager.run
    (project / 'change.txt').write_text('change')
    def fail_commit(*args):
        if args[0] == 'commit':
            return subprocess.CompletedProcess(args, 1, '', 'hook rejected commit')
        return original(*args)
    monkeypatch.setattr(manager, 'run', fail_commit)
    with pytest.raises(RuntimeError, match='hook rejected'):
        manager.commit_all('change')


def test_stop_file_prevents_invocation(project):
    (project / 'phases/STOP').write_text('stop')
    ex = executor(project, lambda *a, **k: ok(), auto_commit=False)
    with pytest.raises(RuntimeError, match='STOP'):
        ex.run()
    assert not ex._backend.invoke.called


def test_dependencies_keep_transitive_context_and_execution_order():
    index = {'steps': [
        {'step': 0, 'name': 'early', 'status': 'completed', 'summary': 'important contract'},
        {'step': 1, 'name': 'unrelated', 'status': 'completed', 'summary': 'irrelevant'},
        {'step': 2, 'name': 'middle', 'status': 'completed', 'depends_on': [0], 'summary': 'middle contract'},
        {'step': 3, 'name': 'later', 'status': 'pending', 'depends_on': [4]},
        {'step': 4, 'name': 'current', 'status': 'pending', 'depends_on': [2]},
    ]}
    assert StepExecutor._select_next_step(index)['step'] == 4
    context = PromptBuilder.build_step_context(index, index['steps'][4])
    assert 'important contract' in context and 'middle contract' in context
    assert 'irrelevant' not in context


def test_native_rules_are_not_inlined_and_no_framework_fallback(tmp_path):
    root, framework = tmp_path / 'target', tmp_path / 'framework'
    root.mkdir()
    framework.mkdir()
    (framework / 'AGENTS.md').write_text('wrong project tests')
    assert PromptBuilder.load_guardrails(root, framework, []) == ''
    (root / 'AGENTS.md').write_text('target policy')
    native = PromptBuilder.load_guardrails(root, framework, [], 'native')
    assert 'AGENTS.md' in native and 'target policy' not in native
    assert 'target policy' in PromptBuilder.load_guardrails(root, framework, [], 'inline')


def test_prior_context_does_not_grow_with_unrelated_history():
    steps = [{'step': i, 'name': 'past', 'status': 'completed', 'summary': 'x' * 1000} for i in range(500)]
    context = PromptBuilder.build_step_context({'steps': steps}, {'depends_on': []})
    assert len(context) < 200
    assert 'index.json' in context


def test_safe_review_text_reaches_real_process(project):
    backend = GenericCommandBackend('echo', [sys.executable, '-c', 'import sys; print(sys.argv[1])', '{prompt}'], [])
    prompt = 'Review git reset --hard and DROP TABLE usage; do not execute them.'
    result = backend.invoke(prompt, cwd=str(project), timeout=5)
    assert result.exit_code == 0 and prompt in result.stdout


def test_missing_cli_and_timeout_are_reported(project):
    missing = GenericCommandBackend('missing', ['/not/a/real/agent'], [])
    assert missing.invoke('task', cwd=str(project), timeout=1).failure_kind == 'configuration'
    slow = GenericCommandBackend('slow', [sys.executable, '-c', 'import time; time.sleep(10)', '{prompt}'], [])
    result = slow.invoke('task', cwd=str(project), timeout=0.1)
    assert result.exit_code == 124 and result.failure_kind == 'timeout'


def test_structured_failure_is_not_success_and_error_tail_is_preserved(project):
    event = json.dumps({'type': 'result', 'is_error': True, 'result': 'Invalid API key'})
    backend = GenericCommandBackend('fake', [sys.executable, '-c', f'print({event!r})', '{prompt}'], [])
    result = backend.invoke('task', cwd=str(project), timeout=5)
    assert result.exit_code != 0 and result.failure_kind == 'configuration'
    assert 'specific last error' in diagnostic('x' * 10000 + '\nspecific last error', '')


def test_corrupt_manifest_is_preserved_and_recovery_is_idempotent(project):
    manifest = project / 'phases/project-manifest.json'
    manifest.write_text('{broken')
    with pytest.raises(ValueError, match='preserved'):
        update_project_manifest(project / 'phases', '0-test', {'project': 'test'})
    assert manifest.read_text() == '{broken'
    manifest.unlink()
    baseline = {'project': 'test', 'known_issues': ['issue']}
    update_project_manifest(project / 'phases', '0-test', baseline)
    first = manifest.read_bytes()
    update_project_manifest(project / 'phases', '0-test', baseline)
    assert manifest.read_bytes() == first


def test_atomic_state_preserves_original_on_failed_replace(project, monkeypatch):
    path = project / 'phases/0-test/index.json'
    original = path.read_bytes()
    def fail(*args):
        raise OSError('simulated interruption')
    monkeypatch.setattr('harness.state.os.replace', fail)
    with pytest.raises(OSError):
        write_json(path, {'steps': []})
    assert path.read_bytes() == original
    assert not list(path.parent.glob('.index.json.*'))


def test_real_cli_pipeline_commits_final_state_and_resumes_without_reexecution(project):
    # Real subprocess + real Git + independent check; only the LLM is replaced by a tiny CLI fixture.
    stub = project / 'fake_agent.py'
    stub.write_text('''import json
from pathlib import Path
p = Path("phases/0-test/index.json")
index = json.loads(p.read_text())
index["steps"][0].update(status="completed", summary="feature produced")
Path("feature.txt").write_text("expected behavior")
p.write_text(json.dumps(index))
print(json.dumps({"type":"result", "is_error":False}))
''')
    index = read_index(project)
    index['steps'][0]['checks'] = [[sys.executable, '-c', 'from pathlib import Path; assert Path("feature.txt").read_text() == "expected behavior"']]
    save_index(project, index)
    write_json(project / 'harness.json', {'default_backend': 'fixture', 'backends': {
        'fixture': {'command': [sys.executable, str(stub), '{prompt}']},
    }})
    GitManager(str(project)).commit_all('configure fixture')
    script = Path(__file__).resolve().parents[1] / 'scripts/execute.py'
    command = [sys.executable, str(script), '0-test', '--root', str(project)]
    first = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert first.returncode == 0, first.stdout + first.stderr
    manager = GitManager(str(project))
    assert manager.checked('status', '--porcelain').stdout == ''
    head = manager.checked('rev-parse', 'HEAD').stdout
    committed = json.loads(manager.checked('show', 'HEAD:phases/0-test/index.json').stdout)
    assert committed['completed_at'] and committed['steps'][0]['verification']['source'] == 'executor'
    second = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert second.returncode == 0, second.stdout + second.stderr
    assert manager.checked('rev-parse', 'HEAD').stdout == head


def test_stop_during_gate_does_not_leave_unverified_completion(project):
    index = read_index(project)
    index['steps'][0]['checks'] = [[sys.executable, '-c', 'print("check")']]
    save_index(project, index)
    def invoke(*a, **k):
        complete(project)
        (project / 'phases/STOP').write_text('pause')
        return ok()
    with pytest.raises(RuntimeError, match='STOP'):
        executor(project, invoke, auto_commit=False).run()
    assert read_index(project)['steps'][0]['status'] == 'pending'
    assert 'completed_at' not in read_index(project)


def test_stale_verification_is_not_reused(project):
    index = read_index(project)
    index['steps'][0]['verification'] = {'status': 'passed', 'details': 'old code passed'}
    save_index(project, index)
    def invoke(*a, **k):
        index = read_index(project)
        index['steps'][0].update(status='completed', summary='new implementation')
        save_index(project, index)
        return ok()
    with pytest.raises(RuntimeError, match='verification'):
        executor(project, invoke, auto_commit=False).run()


def test_recovered_transport_error_is_not_a_failed_turn(project):
    from harness.backends.generic import structured_errors
    assert not structured_errors('\n'.join([
        json.dumps({'type': 'error', 'message': 'Reconnecting'}),
        json.dumps({'type': 'turn.completed', 'usage': {}}),
    ]))


def test_backend_overrides_preserve_defaults_and_support_native_mode(project):
    write_json(project / 'harness.json', {'backends': {'codex': {'guardrail_files': ['EXTRA.md']}}})
    ex = StepExecutor(project, '0-test', backend_name='codex')
    assert ex._backend.instruction_mode == 'native'
    assert '--sandbox' in ex._backend._command_template
    write_json(project / 'harness.json', {'backends': {'codex': {'command': ['custom', '{prompt}']}}})
    assert StepExecutor(project, '0-test', backend_name='codex')._backend.instruction_mode == 'inline'


def test_finalization_can_resume_after_manifest_repair(project):
    def invoke(*a, **k):
        complete(project)
        return ok()
    manifest = project / 'phases/project-manifest.json'
    manifest.write_text('{broken')
    ex = executor(project, invoke, auto_commit=False)
    with pytest.raises(ValueError, match='preserved'):
        ex.run()
    assert manifest.read_text() == '{broken'
    manifest.write_text('{}')
    ex.run()
    assert ex._backend.invoke.call_count == 1
    assert json.loads(manifest.read_text())['phase_history'][0]['phase'] == '0-test'
