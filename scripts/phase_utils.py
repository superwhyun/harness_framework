"""
Phase scaffolding and validation helpers shared by harness scripts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VALID_STEP_STATUSES = {"pending", "completed", "error", "blocked"}
PLACEHOLDER_PATTERN = re.compile(r"^\{replace-with-")
STEP_REQUIRED_HEADINGS = [
    "## 읽어야 할 파일",
    "## 모듈 할당",
    "## 계약 및 베이스라인",
    "## 작업",
    "## Acceptance Criteria",
    "## 검증 절차",
    "## 금지사항",
]
LEGACY_STEP_REQUIRED_HEADINGS = [
    "## 읽어야 할 파일",
    "## 작업",
    "## Acceptance Criteria",
    "## 검증 절차",
    "## 금지사항",
]
STEP_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def read_json_file(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path} not found"
    except json.JSONDecodeError as exc:
        return None, f"{path} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"


def write_json_file(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_template(root: Path, name: str) -> str:
    template_path = root / "templates" / name
    return template_path.read_text(encoding="utf-8")


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def default_module_entry(step_name: str, step_index: int) -> dict:
    return {
        "name": step_name,
        "owner_steps": [step_index],
        "owned_paths": [f"{{replace-with-{step_name}-owned-paths}}"],
        "contracts": [f"{{replace-with-{step_name}-public-contracts}}"],
        "dependencies": [],
        "status": "planned",
    }


def scaffold_phase(
    root: Path,
    phase_dir_name: str,
    project: str,
    phase_name: str,
    step_names: list[str],
    *,
    template_root: Path | None = None,
    force: bool = False,
):
    phases_dir = root / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    (phases_dir / "baselines").mkdir(parents=True, exist_ok=True)
    phase_dir = phases_dir / phase_dir_name
    phase_dir.mkdir(parents=True, exist_ok=True)

    top_index_path = phases_dir / "index.json"
    top_index, error = read_json_file(top_index_path)
    if top_index is None:
        top_index = {"phases": []}
    elif error:
        raise ValueError(error)

    if not any(item.get("dir") == phase_dir_name for item in top_index.get("phases", [])):
        top_index.setdefault("phases", []).append({"dir": phase_dir_name, "status": "pending"})
    write_json_file(top_index_path, top_index)

    phase_index = {
        "schema_version": 2,
        "project": project,
        "phase": phase_name,
        "execution_policy": {
            "context_mode": "contract-first",
            "blocking_fix_priority": True,
            "append_only_steps": True,
        },
        "steps": [{"step": index, "name": name, "status": "pending"} for index, name in enumerate(step_names)],
    }
    write_json_file(phase_dir / "index.json", phase_index)

    step_template = load_template(template_root or root, "step.md.tmpl")
    for index, step_name in enumerate(step_names):
        step_path = phase_dir / f"step{index}.md"
        if step_path.exists() and not force:
            continue
        step_path.write_text(
            render_template(
                step_template,
                {
                    "step_number": str(index),
                    "step_name": step_name,
                },
            ),
            encoding="utf-8",
        )

    module_map_template_path = (template_root or root) / "templates" / "module-map.json.tmpl"
    module_map_path = phase_dir / "module-map.json"
    if force or not module_map_path.exists():
        if module_map_template_path.exists():
            module_map_template = module_map_template_path.read_text(encoding="utf-8")
            rendered_module_map = render_template(
                module_map_template,
                {
                    "phase_dir": phase_dir_name,
                    "project": project,
                    "first_step_name": step_names[0],
                },
            )
            try:
                module_map = json.loads(rendered_module_map)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{module_map_template_path} is not valid JSON: {exc.msg}") from exc
        else:
            module_map = {
                "schema_version": 1,
                "phase": phase_dir_name,
                "policy": {"context_mode": "contract-first"},
                "modules": [],
            }

        modules = module_map.setdefault("modules", [])
        owner_steps = {
            owner_step
            for module in modules
            if isinstance(module, dict)
            for owner_step in module.get("owner_steps", [])
            if isinstance(owner_step, int)
        }
        for index, step_name in enumerate(step_names):
            if index not in owner_steps:
                modules.append(default_module_entry(step_name, index))

        write_json_file(module_map_path, module_map)


def validate_phase_bundle(root: Path, phase_dir_name: str) -> list[str]:
    errors: list[str] = []
    phases_dir = root / "phases"
    phase_dir = phases_dir / phase_dir_name

    top_index_path = phases_dir / "index.json"
    if top_index_path.exists():
        top_index, error = read_json_file(top_index_path)
        if error:
            errors.append(error)
        elif not isinstance(top_index.get("phases"), list):
            errors.append(f"{top_index_path} must contain a phases array")
        else:
            for item in top_index["phases"]:
                status = item.get("status")
                if status not in VALID_STEP_STATUSES:
                    errors.append(f"{top_index_path} contains invalid status: {status}")

    phase_index_path = phase_dir / "index.json"
    phase_index, error = read_json_file(phase_index_path)
    if error:
        errors.append(error)
        return errors

    project = phase_index.get("project")
    if not isinstance(project, str) or not project.strip():
        errors.append(f"{phase_index_path} must contain a non-empty project")

    phase_name = phase_index.get("phase")
    if not isinstance(phase_name, str) or not phase_name.strip():
        errors.append(f"{phase_index_path} must contain a non-empty phase")

    schema_version = phase_index.get("schema_version", 1)
    if not isinstance(schema_version, int) or schema_version < 1:
        errors.append(f"{phase_index_path} schema_version must be a positive integer")
        schema_version = 1

    if schema_version >= 2:
        _validate_module_map(phase_dir / "module-map.json", errors)

    steps = phase_index.get("steps")
    if not isinstance(steps, list):
        errors.append(f"{phase_index_path} must contain a steps array")
        return errors

    for expected_step, step in enumerate(steps):
        if step.get("step") != expected_step:
            errors.append(f"{phase_index_path} step ordering must start at 0 and be contiguous")

        name = step.get("name")
        if not isinstance(name, str) or not STEP_NAME_PATTERN.fullmatch(name):
            errors.append(f"{phase_index_path} step {expected_step} name must be kebab-case")

        status = step.get("status")
        if status not in VALID_STEP_STATUSES:
            errors.append(f"{phase_index_path} step {expected_step} has invalid status: {status}")

        if status == "completed" and not step.get("summary"):
            errors.append(f"{phase_index_path} step {expected_step} is completed but missing summary")
        if status == "error" and not step.get("error_message"):
            errors.append(f"{phase_index_path} step {expected_step} is error but missing error_message")
        if status == "blocked" and not step.get("blocked_reason"):
            errors.append(f"{phase_index_path} step {expected_step} is blocked but missing blocked_reason")

        step_path = phase_dir / f"step{expected_step}.md"
        if not step_path.exists():
            errors.append(f"{step_path} not found")
            continue

        step_text = step_path.read_text(encoding="utf-8")
        required_headings = STEP_REQUIRED_HEADINGS if schema_version >= 2 else LEGACY_STEP_REQUIRED_HEADINGS
        for heading in required_headings:
            if heading not in step_text:
                errors.append(f"{step_path} is missing heading: {heading}")

    return errors


def _validate_module_map(module_map_path: Path, errors: list[str]) -> None:
    module_map, error = read_json_file(module_map_path)
    if error:
        errors.append(error)
        return

    schema_version = module_map.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        errors.append(f"{module_map_path} schema_version must be a positive integer")

    policy = module_map.get("policy")
    if not isinstance(policy, dict):
        errors.append(f"{module_map_path} must contain a policy object")
    elif policy.get("context_mode") != "contract-first":
        errors.append(f"{module_map_path} policy.context_mode must be contract-first")

    modules = module_map.get("modules")
    if not isinstance(modules, list) or not modules:
        errors.append(f"{module_map_path} must contain a non-empty modules array")
        return

    for index, module in enumerate(modules):
        if not isinstance(module, dict):
            errors.append(f"{module_map_path} module {index} must be an object")
            continue

        name = module.get("name")
        if not isinstance(name, str) or not STEP_NAME_PATTERN.fullmatch(name):
            errors.append(f"{module_map_path} module {index} name must be kebab-case")

        owner_steps = module.get("owner_steps")
        if not isinstance(owner_steps, list) or not owner_steps or not all(isinstance(item, int) for item in owner_steps):
            errors.append(f"{module_map_path} module {name or index} owner_steps must be a non-empty integer array")

        owned_paths = module.get("owned_paths")
        if not isinstance(owned_paths, list) or not owned_paths or not all(isinstance(item, str) and item for item in owned_paths):
            errors.append(f"{module_map_path} module {name or index} owned_paths must be a non-empty string array")
        elif any(PLACEHOLDER_PATTERN.match(p) for p in owned_paths if isinstance(p, str)):
            errors.append(f"{module_map_path} module {name or index} owned_paths contains unfilled placeholder")

        contracts = module.get("contracts")
        # Empty contracts array is allowed for modules still in "planned" status (Step 0 pre-fill).
        # Once a module is active, contracts should be populated.
        if not isinstance(contracts, list) or not all(isinstance(item, str) and item for item in contracts):
            errors.append(f"{module_map_path} module {name or index} contracts must be a string array")
        elif any(PLACEHOLDER_PATTERN.match(c) for c in contracts if isinstance(c, str)):
            errors.append(f"{module_map_path} module {name or index} contracts contains unfilled placeholder")

        dependencies = module.get("dependencies")
        if not isinstance(dependencies, list) or not all(isinstance(item, str) and item for item in dependencies):
            errors.append(f"{module_map_path} module {name or index} dependencies must be a string array")
