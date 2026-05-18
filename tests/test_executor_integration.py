"""
Integration tests for StepExecutor core loop with mock backends.
"""

import json
import subprocess
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
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
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
    executor._execute_all_steps("", "")

    idx = json.loads((root / "phases" / "0-test" / "index.json").read_text(encoding="utf-8"))
    assert all(s["status"] == "completed" for s in idx["steps"])



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
    executor._execute_all_steps("", "")

    assert call_count == 2
    idx = json.loads((root / "phases" / "0-retry" / "index.json").read_text(encoding="utf-8"))
    assert idx["steps"][0]["status"] == "completed"



def test_step_executor_prioritizes_blocking_fix_and_unblocks_step():
    root = _make_project("0-blocking", ["blocked-module", "normal-step", "fix-contract"])
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    phase_index_path = root / "phases" / "0-blocking" / "index.json"
    index = json.loads(phase_index_path.read_text(encoding="utf-8"))
    index["steps"][0]["status"] = "blocked"
    index["steps"][0]["blocked_reason"] = "contract mismatch"
    index["steps"][0]["blocked_by_step"] = 2
    index["steps"][2]["kind"] = "blocking-fix"
    index["steps"][2]["unblocks"] = [0]
    phase_index_path.write_text(json.dumps(index), encoding="utf-8")

    executor = StepExecutor(root=root, phase_dir_name="0-blocking", backend_name="claude")

    next_step = executor._select_next_step(index)
    assert next_step["step"] == 2

    released = executor._release_blocked_steps(index, index["steps"][2])

    assert released == [0]
    assert index["steps"][0]["status"] == "pending"
    assert index["steps"][0]["unblocked_by_step"] == 2


def test_step_executor_writes_phase_baseline():
    root = _make_project("0-baseline", ["step-a"])
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    phase_dir = root / "phases" / "0-baseline"
    (phase_dir / "module-map.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy": {"context_mode": "contract-first"},
                "modules": [
                    {
                        "name": "step-a",
                        "owner_steps": [0],
                        "owned_paths": ["src/step-a/**"],
                        "contracts": ["src/contracts/step-a.ts"],
                        "dependencies": [],
                    }
                ],
                "shared_contracts": ["src/contracts/shared.ts"],
                "integration_points": ["src/router.ts"],
            }
        ),
        encoding="utf-8",
    )
    executor = StepExecutor(root=root, phase_dir_name="0-baseline", backend_name="claude")
    index = json.loads((phase_dir / "index.json").read_text(encoding="utf-8"))
    index["steps"][0]["status"] = "completed"
    index["steps"][0]["summary"] = "done"
    index["completed_at"] = "2026-05-13T00:00:00+0900"

    executor._write_phase_baseline(index)

    baseline = json.loads((root / "phases" / "baselines" / "0-baseline.json").read_text(encoding="utf-8"))
    assert baseline["source_module_map"] == "phases/0-baseline/module-map.json"
    assert baseline["modules"][0]["name"] == "step-a"
    assert baseline["shared_contracts"] == ["src/contracts/shared.ts"]
    assert baseline["integration_points"] == ["src/router.ts"]


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
