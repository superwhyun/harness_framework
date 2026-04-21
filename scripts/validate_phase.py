#!/usr/bin/env python3
"""
Validate a harness phase directory and its step files.
"""

import argparse
import sys
from pathlib import Path

from phase_utils import validate_phase_bundle


def main():
    parser = argparse.ArgumentParser(description="Validate a harness phase")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--root", help="Repository root; defaults to current working directory")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path.cwd()
    errors = validate_phase_bundle(root, args.phase_dir)
    if errors:
        print("Phase validation failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print(f"Phase {args.phase_dir} is valid")


if __name__ == "__main__":
    main()
