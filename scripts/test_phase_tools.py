import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase_utils import scaffold_phase, validate_phase_bundle
from harness.project_context import read_active_project, resolve_project_root, write_active_project


def test_scaffold_phase_creates_valid_bundle(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "step.md.tmpl").write_text(
        "# Step {{step_number}}: {{step_name}}\n\n"
        "## 읽어야 할 파일\n\n- /docs/ARCHITECTURE.md\n\n"
        "## 작업\n\n설명\n\n"
        "## Acceptance Criteria\n\n```bash\nnpm test\n```\n\n"
        "## 검증 절차\n\n1. 테스트\n\n"
        "## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )

    scaffold_phase(tmp_path, "0-mvp", "Demo", "mvp", ["project-setup", "api-layer"])

    phase_index = json.loads((tmp_path / "phases" / "0-mvp" / "index.json").read_text(encoding="utf-8"))
    assert phase_index["project"] == "Demo"
    assert [step["name"] for step in phase_index["steps"]] == ["project-setup", "api-layer"]
    assert not validate_phase_bundle(tmp_path, "0-mvp")


def test_scaffold_phase_can_use_separate_template_root(tmp_path):
    project_root = tmp_path / "projects" / "demo"
    template_root = tmp_path / "framework"
    (template_root / "templates").mkdir(parents=True)
    (template_root / "templates" / "step.md.tmpl").write_text(
        "# Step {{step_number}}: {{step_name}}\n\n"
        "## 읽어야 할 파일\n\n- /docs/ARCHITECTURE.md\n\n"
        "## 작업\n\nfrom framework template\n\n"
        "## Acceptance Criteria\n\n```bash\nnpm test\n```\n\n"
        "## 검증 절차\n\n1. 테스트\n\n"
        "## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )

    scaffold_phase(project_root, "0-mvp", "Demo", "mvp", ["project-setup"], template_root=template_root)

    step = project_root / "phases" / "0-mvp" / "step0.md"
    assert "from framework template" in step.read_text(encoding="utf-8")


def test_validate_phase_bundle_reports_missing_step_sections(tmp_path):
    phases_dir = tmp_path / "phases" / "0-mvp"
    phases_dir.mkdir(parents=True)
    (tmp_path / "phases" / "index.json").write_text(json.dumps({"phases": [{"dir": "0-mvp", "status": "pending"}]}))
    (phases_dir / "index.json").write_text(
        json.dumps({"project": "Demo", "phase": "mvp", "steps": [{"step": 0, "name": "setup", "status": "pending"}]})
    )
    (phases_dir / "step0.md").write_text("# Step 0: setup\n\n## 작업\n\n설명\n", encoding="utf-8")

    errors = validate_phase_bundle(tmp_path, "0-mvp")

    assert any("Acceptance Criteria" in error for error in errors)


def test_validate_phase_script_runs(tmp_path):
    # Keep this simple: validate a generated phase through the real CLI entrypoint.
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "step.md.tmpl").write_text(
        "# Step {{step_number}}: {{step_name}}\n\n"
        "## 읽어야 할 파일\n\n- /docs/ARCHITECTURE.md\n\n"
        "## 작업\n\n설명\n\n"
        "## Acceptance Criteria\n\n```bash\nnpm test\n```\n\n"
        "## 검증 절차\n\n1. 테스트\n\n"
        "## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )
    scaffold_phase(tmp_path, "0-mvp", "Demo", "mvp", ["project-setup"])

    script = Path(__file__).parent / "validate_phase.py"
    result = subprocess.run(
        [sys.executable, str(script), "0-mvp", "--root", str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_active_project_resolution_uses_state_file(tmp_path):
    project_root = tmp_path / "projects" / "demo"
    write_active_project(tmp_path, Path("projects/demo"))

    assert read_active_project(tmp_path) == "projects/demo"
    assert resolve_project_root(tmp_path) == project_root.resolve()
