#!/usr/bin/env python3
"""
Set or show the active target project for framework-driven harness commands.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.project_context import active_project_file, read_active_project, write_active_project


def main():
    parser = argparse.ArgumentParser(description="Set the active harness target project")
    parser.add_argument("project_root", nargs="?", help="Target project root, e.g. projects/my-project")
    parser.add_argument("--show", action="store_true", help="Print the current active target project")
    args = parser.parse_args()

    if args.show:
        value = read_active_project(ROOT)
        if not value:
            print("No active project configured")
            sys.exit(1)
        print(value)
        return

    if not args.project_root:
        parser.error("project_root is required unless --show is used")

    project_root = Path(args.project_root)
    write_active_project(ROOT, project_root)
    print(f"Active project set to {project_root.as_posix()}")
    print(f"State file: {active_project_file(ROOT)}")


if __name__ == "__main__":
    main()
