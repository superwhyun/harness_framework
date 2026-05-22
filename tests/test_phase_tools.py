import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.phase_utils import scaffold_phase, validate_phase_bundle
from harness.project_context import read_active_project, resolve_project_root, write_active_project
from harness.manifest import update_project_manifest


def _write_step_template(template_root: Path, body: str = "설명"):
    (template_root / "templates").mkdir(parents=True, exist_ok=True)
    (template_root / "templates" / "step.md.tmpl").write_text(
        "# Step {{step_number}}: {{step_name}}\n\n"
        "## 읽어야 할 파일\n\n- /docs/ARCHITECTURE.md\n\n"
        "## 모듈 할당\n\n- module: `{module-name}`\n- owned_paths:\n  - `{path}`\n- read_contracts:\n  - `{contract}`\n- forbidden_paths:\n  - `{forbidden}`\n\n"
        "## 계약 및 베이스라인\n\n- contract-first\n\n"
        f"## 작업\n\n{body}\n\n"
        "## Acceptance Criteria\n\n```bash\nnpm test\n```\n\n"
        "## 검증 절차\n\n1. 테스트\n\n"
        "## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )


def _write_module_map_template(template_root: Path):
    (template_root / "templates").mkdir(parents=True, exist_ok=True)
    (template_root / "templates" / "module-map.json.tmpl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "phase": "{{phase_dir}}",
                "policy": {"context_mode": "contract-first"},
                "modules": [
                    {
                        "name": "{{first_step_name}}",
                        "owner_steps": [0],
                        "owned_paths": ["src/{{first_step_name}}/**"],
                        "contracts": ["src/contracts/{{first_step_name}}.ts"],
                        "dependencies": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_scaffold_phase_creates_valid_bundle(tmp_path):
    _write_step_template(tmp_path)
    _write_module_map_template(tmp_path)

    scaffold_phase(tmp_path, "0-mvp", "Demo", "mvp", ["project-setup", "api-layer"])

    phase_index = json.loads((tmp_path / "phases" / "0-mvp" / "index.json").read_text(encoding="utf-8"))
    assert phase_index["project"] == "Demo"
    assert phase_index["schema_version"] == 2
    assert [step["name"] for step in phase_index["steps"]] == ["project-setup", "api-layer"]
    assert (tmp_path / "phases" / "0-mvp" / "module-map.json").exists()
    module_map = json.loads((tmp_path / "phases" / "0-mvp" / "module-map.json").read_text(encoding="utf-8"))
    modules = module_map["modules"]
    assert len(modules) == 2
    # First module from template (legacy format with name)
    assert modules[0]["name"] == "project-setup"
    # Second module auto-generated (thin format with ref)
    assert modules[1]["ref"] == "docs/modules/api-layer/MODULE.md"
    assert modules[1]["phase_status"] == "planned"


def test_validate_catches_unfilled_placeholder_in_owned_paths(tmp_path):
    _write_step_template(tmp_path)
    phases_dir = tmp_path / "phases" / "0-mvp"
    phases_dir.mkdir(parents=True)
    (tmp_path / "phases" / "index.json").write_text(
        json.dumps({"phases": [{"dir": "0-mvp", "status": "pending"}]})
    )
    (phases_dir / "index.json").write_text(
        json.dumps({"schema_version": 2, "project": "Demo", "phase": "mvp",
                    "steps": [{"step": 0, "name": "setup", "status": "pending"}]})
    )
    (phases_dir / "step0.md").write_text(
        "# Step 0: setup\n\n## 읽어야 할 파일\n\n- AGENTS.md\n\n"
        "## 모듈 할당\n\n- module: setup\n\n## 계약 및 베이스라인\n\n- contract-first\n\n"
        "## 작업\n\n설명\n\n## Acceptance Criteria\n\n- [ ] done\n\n"
        "## 검증 절차\n\n1. 테스트\n\n## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )
    (phases_dir / "module-map.json").write_text(
        json.dumps({
            "schema_version": 1,
            "phase": "0-mvp",
            "policy": {"context_mode": "contract-first"},
            "modules": [{
                "name": "setup",
                "owner_steps": [0],
                "owned_paths": ["{replace-with-setup-owned-paths}"],
                "contracts": ["src/contracts/setup.ts"],
                "dependencies": [],
            }],
        })
    )

    errors = validate_phase_bundle(tmp_path, "0-mvp")

    assert any("owned_paths" in e and "unfilled placeholder" in e for e in errors)


def test_validate_catches_unfilled_placeholder_in_contracts(tmp_path):
    _write_step_template(tmp_path)
    phases_dir = tmp_path / "phases" / "0-mvp"
    phases_dir.mkdir(parents=True)
    (tmp_path / "phases" / "index.json").write_text(
        json.dumps({"phases": [{"dir": "0-mvp", "status": "pending"}]})
    )
    (phases_dir / "index.json").write_text(
        json.dumps({"schema_version": 2, "project": "Demo", "phase": "mvp",
                    "steps": [{"step": 0, "name": "setup", "status": "pending"}]})
    )
    (phases_dir / "step0.md").write_text(
        "# Step 0: setup\n\n## 읽어야 할 파일\n\n- AGENTS.md\n\n"
        "## 모듈 할당\n\n- module: setup\n\n## 계약 및 베이스라인\n\n- contract-first\n\n"
        "## 작업\n\n설명\n\n## Acceptance Criteria\n\n- [ ] done\n\n"
        "## 검증 절차\n\n1. 테스트\n\n## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )
    (phases_dir / "module-map.json").write_text(
        json.dumps({
            "schema_version": 1,
            "phase": "0-mvp",
            "policy": {"context_mode": "contract-first"},
            "modules": [{
                "name": "setup",
                "owner_steps": [0],
                "owned_paths": ["src/setup/**"],
                "contracts": ["{replace-with-setup-public-contracts}"],
                "dependencies": [],
            }],
        })
    )

    errors = validate_phase_bundle(tmp_path, "0-mvp")

    assert any("contracts" in e and "unfilled placeholder" in e for e in errors)


def test_scaffold_phase_can_use_separate_template_root(tmp_path):
    project_root = tmp_path / "projects" / "demo"
    template_root = tmp_path / "framework"
    _write_step_template(template_root, body="from framework template")
    _write_module_map_template(template_root)

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
    _write_step_template(tmp_path)
    _write_module_map_template(tmp_path)
    scaffold_phase(tmp_path, "0-mvp", "Demo", "mvp", ["project-setup"])

    script = Path(__file__).resolve().parent.parent / "scripts" / "validate_phase.py"
    result = subprocess.run(
        [sys.executable, str(script), "0-mvp", "--root", str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_phase_bundle_reports_missing_module_map_for_schema_v2(tmp_path):
    phases_dir = tmp_path / "phases" / "0-mvp"
    phases_dir.mkdir(parents=True)
    (tmp_path / "phases" / "index.json").write_text(json.dumps({"phases": [{"dir": "0-mvp", "status": "pending"}]}))
    (phases_dir / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "project": "Demo",
                "phase": "mvp",
                "steps": [{"step": 0, "name": "setup", "status": "pending"}],
            }
        )
    )
    (phases_dir / "step0.md").write_text(
        "# Step 0: setup\n\n"
        "## 읽어야 할 파일\n\n- AGENTS.md\n\n"
        "## 모듈 할당\n\n- module: setup\n\n"
        "## 계약 및 베이스라인\n\n- contract-first\n\n"
        "## 작업\n\n설명\n\n"
        "## Acceptance Criteria\n\n- [ ] done\n\n"
        "## 검증 절차\n\n1. 테스트\n\n"
        "## 금지사항\n\n- 없음\n",
        encoding="utf-8",
    )

    errors = validate_phase_bundle(tmp_path, "0-mvp")

    assert any("module-map.json" in error for error in errors)


def test_active_project_resolution_uses_state_file(tmp_path):
    project_root = tmp_path / "projects" / "demo"
    write_active_project(tmp_path, Path("projects/demo"))

    assert read_active_project(tmp_path) == "projects/demo"
    assert resolve_project_root(tmp_path) == project_root.resolve()


def _make_baseline(project: str, phase: str, **kwargs) -> dict:
    base = {
        "project": project,
        "phase": phase,
        "tag": f"{project}-{phase}-done",
        "modules": [],
        "routes": [],
        "shared_contracts": [],
        "integration_points": [],
        "known_issues": [],
        "completed_at": "2026-01-01T00:00:00+0900",
    }
    base.update(kwargs)
    return base


def test_project_manifest_created_on_first_phase(tmp_path):
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()
    baseline = _make_baseline(
        "demo", "0-setup",
        modules=[{"name": "auth", "purpose": "JWT 인증", "owned_paths": ["src/auth/**"], "contracts": ["src/contracts/auth.ts"]}],
        routes=[{"method": "POST", "path": "/api/login", "purpose": "로그인"}],
        shared_contracts=[{"path": "src/contracts/user.ts", "purpose": "User 타입"}],
        integration_points=[{"name": "postgres", "type": "database", "purpose": "주 DB"}],
    )

    update_project_manifest(phases_dir, "0-setup", baseline)

    manifest = json.loads((phases_dir / "project-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["modules"]) == 1
    assert manifest["modules"][0]["name"] == "auth"
    assert manifest["modules"][0]["phase"] == "0-setup"
    assert len(manifest["routes"]) == 1
    assert len(manifest["shared_contracts"]) == 1
    assert len(manifest["integration_points"]) == 1
    assert len(manifest["phase_history"]) == 1
    assert manifest["phase_history"][0]["tag"] == "demo-0-setup-done"


def test_project_manifest_accumulates_across_phases(tmp_path):
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()

    update_project_manifest(phases_dir, "0-setup", _make_baseline(
        "demo", "0-setup",
        modules=[{"name": "auth", "purpose": "JWT", "owned_paths": ["src/auth/**"], "contracts": ["src/contracts/auth.ts"]}],
        routes=[{"method": "POST", "path": "/api/login", "purpose": "로그인"}],
    ))
    update_project_manifest(phases_dir, "1-feature", _make_baseline(
        "demo", "1-feature",
        modules=[{"name": "post", "purpose": "게시글", "owned_paths": ["src/post/**"], "contracts": ["src/contracts/post.ts"]}],
        routes=[{"method": "GET", "path": "/api/posts", "purpose": "목록 조회"}],
    ))

    manifest = json.loads((phases_dir / "project-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["modules"]) == 2
    assert {m["name"] for m in manifest["modules"]} == {"auth", "post"}
    assert len(manifest["routes"]) == 2
    assert len(manifest["phase_history"]) == 2


def test_project_manifest_deduplicates_routes(tmp_path):
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()

    route = {"method": "POST", "path": "/api/login", "purpose": "로그인"}
    update_project_manifest(phases_dir, "0-setup", _make_baseline("demo", "0-setup", routes=[route]))
    update_project_manifest(phases_dir, "1-fix", _make_baseline("demo", "1-fix", routes=[route]))

    manifest = json.loads((phases_dir / "project-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["routes"]) == 1


def test_project_manifest_updates_module_on_same_name(tmp_path):
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()

    update_project_manifest(phases_dir, "0-setup", _make_baseline(
        "demo", "0-setup",
        modules=[{"name": "auth", "purpose": "기본 인증", "owned_paths": ["src/auth/**"], "contracts": []}],
    ))
    update_project_manifest(phases_dir, "1-refactor", _make_baseline(
        "demo", "1-refactor",
        modules=[{"name": "auth", "purpose": "JWT + OAuth", "owned_paths": ["src/auth/**"], "contracts": ["src/contracts/auth.ts"]}],
    ))

    manifest = json.loads((phases_dir / "project-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["modules"]) == 1
    assert manifest["modules"][0]["purpose"] == "JWT + OAuth"
    assert manifest["modules"][0]["phase"] == "1-refactor"
