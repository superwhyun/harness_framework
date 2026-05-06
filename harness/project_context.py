from __future__ import annotations

import sys
from pathlib import Path


ACTIVE_PROJECT_FILE = Path(".harness") / "current_project"


def active_project_file(framework_root: Path) -> Path:
    return framework_root / ACTIVE_PROJECT_FILE


def read_active_project(framework_root: Path) -> str | None:
    path = active_project_file(framework_root)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def write_active_project(framework_root: Path, project_root: Path) -> Path:
    path = active_project_file(framework_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{project_root.as_posix()}\n", encoding="utf-8")
    return path


def resolve_project_root(
    framework_root: Path,
    explicit_root: str | None = None,
    *,
    interactive: bool = False,
) -> Path:
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()

    active = read_active_project(framework_root)
    if active:
        active_path = Path(active).expanduser()
        if active_path.is_absolute():
            return active_path.resolve()
        return (framework_root / active_path).resolve()

    if interactive and sys.stdin.isatty():
        value = input("Target project root (for example projects/harness_project_alpha): ").strip()
        if value:
            project_root = (framework_root / value).expanduser().resolve()
            write_active_project(framework_root, Path(value))
            return project_root

    raise RuntimeError(
        "No target project configured. Pass --root or run "
        "`python3 scripts/use_project.py <project-root>`."
    )
