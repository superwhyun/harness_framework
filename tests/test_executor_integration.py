"""
Integration tests for StepExecutor core loop with mock backends.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import sys

# Ensure harness package is importable when running from tests/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.executor import StepExecutor
from harness.backends.base import BackendResult


def _make_project(phase_name: str, steps: list[str]) -> Path:
    root = Path(tempfile.mkdtemp())
    phases_dir = root / "phases"
    phase_dir = phases_dir / phase_name
    phase_dir.mkdir(parents=True)

    index = {
        "project": "test-project",
        "phase": phase_name,
        "steps": [
            {"step": i, "name": name, "status": "pending"}
            for i, name in enumerate(steps)
        ],
    }
    (phase_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    for i, name in enumerate(steps):
        (phase_dir / f"step{i}.md").write_text(
            f"# Step {i}: {name}\n\n## 읽어야 할 파일\n\n- AGENTS.md\n\n## 작업\n\nSet status to completed.\n\n## Acceptance Criteria\n\n- [ ] done\n\n## 검증 절차\n\n```bash\necho ok\n```\n\n## 금지사항\n\n- none\n",
            encoding="utf-8",
        )

    # Initialize git repo
    os.system(f"cd {root} && git init -q")
    os.system(f"cd {root} && git config user.email 'test@test.com'")
    os.system(f"cd {root} && git config user.name 'Test'")
    os.system(f"cd {root} && git add -A && git commit -q -m 'init'")
    return root


def _mock_backend():
    backend = MagicMock()
    backend.name = "mock"
    backend.guardrail_files = []
    backend.invoke.return_value = BackendResult(
        backend="mock",
        command=[],
        exit_code=0,
        stdout="done",
        stderr="",
    )
    return backend


def test_step_executor_runs_pending_steps():
    root = _make_project("0-test", ["step-a", "step-b"])
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    executor = StepExecutor(root=root, phase_dir_name="0-test", backend_name="claude")
    executor._backend = _mock_backend()

    # Simulate backend writing index.json with step 0 completed
    def side_effect(prompt, **kwargs):
        idx = json.loads((root / "phases" / "0-test" / "index.json").read_text(encoding="utf-8"))
        for s in idx["steps"]:
            if s["status"] == "pending":
                s["status"] = "completed"
                s["summary"] = "done"
                break
        (root / "phases" / "0-test" / "index.json").write_text(
            json.dumps(idx), encoding="utf-8"
        )
        return BackendResult(backend="mock", command=[], exit_code=0, stdout="ok", stderr="")

    executor._backend.invoke.side_effect = side_effect
    executor._execute_all_steps("")

    idx = json.loads((root / "phases" / "0-test" / "index.json").read_text(encoding="utf-8"))
    assert all(s["status"] == "completed" for s in idx["steps"])

    # Verify stepN-output.json was created
    assert (root / "phases" / "0-test" / "step0-output.json").exists()
    assert (root / "phases" / "0-test" / "step1-output.json").exists()


def test_step_executor_retry_on_failure():
    root = _make_project("0-retry", ["step-a"])
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    executor = StepExecutor(root=root, phase_dir_name="0-retry", backend_name="claude")
    executor.MAX_RETRIES = 2

    call_count = 0

    def side_effect(prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return BackendResult(backend="mock", command=[], exit_code=1, stdout="", stderr="error")
        # Second attempt succeeds
        idx = json.loads((root / "phases" / "0-retry" / "index.json").read_text(encoding="utf-8"))
        idx["steps"][0]["status"] = "completed"
        idx["steps"][0]["summary"] = "done"
        (root / "phases" / "0-retry" / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        return BackendResult(backend="mock", command=[], exit_code=0, stdout="ok", stderr="")

    backend = _mock_backend()
    backend.invoke.side_effect = side_effect
    executor._backend = backend
    executor._execute_all_steps("")

    assert call_count == 2
    idx = json.loads((root / "phases" / "0-retry" / "index.json").read_text(encoding="utf-8"))
    assert idx["steps"][0]["status"] == "completed"


def test_step_executor_output_fields():
    root = _make_project("0-output", ["step-a"])
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    executor = StepExecutor(root=root, phase_dir_name="0-output", backend_name="claude")

    def side_effect(prompt, **kwargs):
        idx = json.loads((root / "phases" / "0-output" / "index.json").read_text(encoding="utf-8"))
        idx["steps"][0]["status"] = "completed"
        idx["steps"][0]["summary"] = "done"
        (root / "phases" / "0-output" / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        return BackendResult(backend="mock", command=[], exit_code=0, stdout="ok", stderr="")

    backend = _mock_backend()
    backend.invoke.side_effect = side_effect
    executor._backend = backend
    executor._execute_all_steps("")

    out_path = root / "phases" / "0-output" / "step0-output.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "summary" in data
    assert "files_changed" in data
    assert "verification" in data
    assert "known_issues" in data
    assert "next_actions" in data
    assert "resume_hint" in data
    assert data["next_actions"] == "phase complete"


def test_git_checkout_failure_is_fatal():
    root = _make_project("0-git", ["step-a"])
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    executor = StepExecutor(root=root, phase_dir_name="0-git", backend_name="claude")
    backend = _mock_backend()
    executor._backend = backend

    import subprocess
    original_run = subprocess.run

    def fake_run(cmd, **kwargs):
        class FakeResult:
            returncode = 1
            stdout = ""
            stderr = "fatal: not a git repository"
        return FakeResult()

    subprocess.run = fake_run
    try:
        import pytest
        with pytest.raises(SystemExit):
            executor._git.checkout("feat-test")
    except ImportError:
        try:
            executor._git.checkout("feat-test")
            assert False, "Expected SystemExit"
        except SystemExit:
            pass
    finally:
        subprocess.run = original_run
