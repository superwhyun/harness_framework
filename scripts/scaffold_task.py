#!/usr/bin/env python3
"""Create one task record in an existing repository without overwriting it."""

import argparse
from pathlib import Path
import re


TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "task.md.tmpl"


def scaffold_task(root: Path, name: str, units=None) -> Path:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("task name must be kebab-case (for example login-fix)")
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"target repository directory does not exist: {root}")
    task_dir = root / "tasks"
    # Do not follow task-directory links outside the requested repository.
    if task_dir.is_symlink():
        raise ValueError("tasks directory must not be a symbolic link")
    units = units or ['implementation', 'integration']
    if len(units) < 2 or len(set(units)) != len(units) or any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', u) for u in units):
        raise ValueError('Provide at least two distinct kebab-case unit names; the last is integration')
    sections = []
    for number, unit in enumerate(units, 1):
        dependency = f"{number - 1:02d}" if number > 1 else "없음"
        sections.append(f"""### {number:02d}. {unit}

- 상태: pending
- 범위와 결과물:
- 선행 단위: {dependency}
- 완료 조건:
- 검증 방법:
- 검증 결과: 미실행
- 구현 요약·남은 문제:
""")
    body = TEMPLATE.read_text(encoding="utf-8").replace("{{task_name}}", name).replace("{{units}}", "\n".join(sections))
    task_dir.mkdir(exist_ok=True)
    path = task_dir / f"{name}.md"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(body)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Task name in kebab-case")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Existing repository (default: cwd)")
    parser.add_argument("--units", nargs="+", help="Planned unit names; last unit verifies the integrated result")
    args = parser.parse_args()
    try:
        print(scaffold_task(args.root, args.name, args.units))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
