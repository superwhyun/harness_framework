#!/usr/bin/env python3
"""
Create a standardized phase skeleton from templates.
"""

import argparse
from pathlib import Path

from phase_utils import scaffold_phase


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new harness phase")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--phase-name", help="Display phase name; defaults to phase_dir")
    parser.add_argument("--steps", nargs="+", required=True, help="Ordered kebab-case step names")
    parser.add_argument("--force", action="store_true", help="Overwrite existing step markdown files")
    parser.add_argument("--root", help="Repository root; defaults to current working directory")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path.cwd()
    scaffold_phase(
        root,
        args.phase_dir,
        args.project,
        args.phase_name or args.phase_dir,
        args.steps,
        force=args.force,
    )
    print(f"Scaffolded phase {args.phase_dir}")


if __name__ == "__main__":
    main()
