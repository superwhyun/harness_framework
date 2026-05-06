#!/usr/bin/env python3
"""
Validate a harness phase directory and its step files.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.phase_utils import validate_phase_bundle
from harness.project_context import resolve_project_root


def main():
    parser = argparse.ArgumentParser(description="Validate a harness phase")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--root", help="Target project root; defaults to .harness/current_project")
    args = parser.parse_args()

    try:
        root = resolve_project_root(ROOT, args.root, interactive=True)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    errors = validate_phase_bundle(root, args.phase_dir)
    if errors:
        print("Phase validation failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print(f"Phase {args.phase_dir} is valid")


if __name__ == "__main__":
    main()
