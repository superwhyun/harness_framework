"""
Phase scaffolding and validation helpers shared by harness scripts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VALID_STEP_STATUSES = {"pending", "completed", "error", "blocked"}
STEP_REQUIRED_HEADINGS = [
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


def scaffold_phase(root: Path, phase_dir_name: str, project: str, phase_name: str, step_names: list[str], *, force: bool = False):
    phases_dir = root / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
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
        "project": project,
        "phase": phase_name,
        "steps": [{"step": index, "name": name, "status": "pending"} for index, name in enumerate(step_names)],
    }
    write_json_file(phase_dir / "index.json", phase_index)

    step_template = load_template(root, "step.md.tmpl")
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
        for heading in STEP_REQUIRED_HEADINGS:
            if heading not in step_text:
                errors.append(f"{step_path} is missing heading: {heading}")

    return errors
