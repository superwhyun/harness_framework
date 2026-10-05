import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.prompt_builder import PromptBuilder
from scripts.phase_utils import scaffold_phase
from scripts.scaffold_task import scaffold_task


ROOT = Path(__file__).resolve().parent.parent


def test_task_cli_uses_cwd_without_active_project(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/scaffold_task.py"), "login-fix"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "tasks/login-fix.md").is_file()
    assert not (tmp_path / "phases").exists()


def test_task_does_not_overwrite_existing_record(tmp_path):
    task = scaffold_task(tmp_path, "login-fix")
    task.write_text("existing progress", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scaffold_task(tmp_path, "login-fix")
    assert task.read_text() == "existing progress"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "task/name", "", "two words"])
def test_task_rejects_invalid_names_before_writing(tmp_path, name):
    with pytest.raises(ValueError):
        scaffold_task(tmp_path, name)
    assert not (tmp_path / "tasks").exists()


def test_task_rejects_missing_target(tmp_path):
    target = tmp_path / "missing"
    with pytest.raises(ValueError):
        scaffold_task(target, "example")
    assert not target.exists()


def test_task_does_not_follow_directory_symlink(tmp_path):
    project, outside = tmp_path / "project", tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (project / "tasks").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        scaffold_task(project, "example")
    assert list(outside.iterdir()) == []


def test_existing_phase_and_top_state_remain_unchanged(tmp_path):
    phase = tmp_path / "phases/0-test"
    phase.mkdir(parents=True)
    (phase / "index.json").write_text('{"steps": [{"status": "completed"}]}')
    (phase / "step0.md").write_text("completed work")
    (tmp_path / "phases/index.json").write_text('{"phases": []}')
    before = {p: p.read_bytes() for p in (tmp_path / "phases").rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        scaffold_phase(tmp_path, "0-test", "demo", "test", ["new-work"], force=True)
    assert {p: p.read_bytes() for p in before} == before


def test_prompt_does_not_inject_framework_docs_into_target(tmp_path):
    framework, target = tmp_path / "framework", tmp_path / "target"
    framework.mkdir()
    target.mkdir()
    (framework / "AGENTS.md").write_text("framework rules")
    (framework / "CLAUDE.md").write_text("framework supplement")
    (framework / "docs").mkdir()
    (framework / "docs/guide.md").write_text("unrelated framework guide")
    (target / "AGENTS.md").write_text("target rules")
    assert PromptBuilder.load_guardrails(target, framework, ["AGENTS.md", "CLAUDE.md"]) == (
        "## 대상 규칙 (AGENTS.md)\n\ntarget rules"
    )


def test_default_hooks_have_no_turn_end_side_effects():
    for name in [".claude/settings.json", ".codex/hooks.json"]:
        assert json.loads((ROOT / name).read_text())["hooks"] == {}


@pytest.mark.parametrize("units", [["only"], ["api", "api"], ["../escape", "integration"], ["api\ninjected", "integration"]])
def test_invalid_units_do_not_create_record(tmp_path, units):
    with pytest.raises(ValueError):
        scaffold_task(tmp_path, "example", units)
    assert not (tmp_path / "tasks").exists()


def test_scaffold_custom_units_creates_only_requested_record(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/scaffold_task.py"), "login",
         "--root", str(tmp_path), "--units", "api", "ui", "integration"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    path = tmp_path / "tasks/login.md"
    assert [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()] == ["tasks/login.md"]
    body = path.read_text()
    assert all(name in body for name in ("api", "ui", "integration"))
    assert "{{" not in body
