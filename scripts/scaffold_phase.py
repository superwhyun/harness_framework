#!/usr/bin/env python3
"""
Create a standardized phase skeleton from templates.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from phase_utils import scaffold_phase
from harness.project_context import resolve_project_root


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new harness phase")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--phase-name", help="Display phase name; defaults to phase_dir")
    parser.add_argument("--steps", nargs="+", required=True, help="Ordered kebab-case step names")
    parser.add_argument("--force", action="store_true", help="Overwrite existing step markdown files")
    parser.add_argument("--root", help="Target project root; defaults to .harness/current_project")
    parser.add_argument("--template-root", help="Template root; defaults to the harness framework root")
    args = parser.parse_args()

    try:
        root = resolve_project_root(ROOT, args.root, interactive=True)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    template_root = Path(args.template_root).resolve() if args.template_root else ROOT
    scaffold_phase(
        root,
        args.phase_dir,
        args.project,
        args.phase_name or args.phase_dir,
        args.steps,
        template_root=template_root,
        force=args.force,
    )
    print(f"Scaffolded phase {args.phase_dir}")


if __name__ == "__main__":
    main()
