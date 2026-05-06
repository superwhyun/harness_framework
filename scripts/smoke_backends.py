#!/usr/bin/env python3
"""
Smoke-check installed backend CLIs against the command surface expected by the harness.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from harness.executor import StepExecutor


HELP_CHECKS = {
    "claude": {
        "command": ["claude", "--help"],
        "contains": ["--output-format", "-p, --print"],
    },
    "codex": {
        "command": ["codex", "exec", "--help"],
        "contains": ["--json", "--dangerously-bypass-approvals-and-sandbox"],
    },
    "gemini": {
        "command": ["gemini", "--help"],
        "contains": ["--output-format", "--approval-mode"],
    },
    "kimi": {
        "command": ["kimi", "--help"],
        "contains": ["--print", "--output-format"],
    },
    "ollama": {
        "command": ["ollama", "--help"],
        "contains": ["Large language model runner"],
    },
    "lmstudio": {
        "command": ["lms", "--help"],
        "contains": ["lms", "LM Studio"],
    },
}


def available_backends() -> list[str]:
    return sorted(StepExecutor.DEFAULT_BACKENDS)


def run_help_check(name: str, cwd: Path) -> list[str]:
    errors = []
    spec = HELP_CHECKS[name]
    binary = spec["command"][0]
    if shutil.which(binary) is None:
        return [f"{name}: binary '{binary}' not found on PATH"]

    result = subprocess.run(spec["command"], cwd=cwd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        errors.append(f"{name}: help command failed with exit code {result.returncode}")
        return errors

    for needle in spec["contains"]:
        if needle not in output:
            errors.append(f"{name}: help output is missing expected flag text '{needle}'")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Smoke-check harness backend CLIs")
    parser.add_argument("--backend", action="append", choices=available_backends(), help="Backend(s) to check")
    args = parser.parse_args()

    backends = args.backend or available_backends()
    cwd = Path(__file__).resolve().parent.parent
    errors = []
    for backend in backends:
        errors.extend(run_help_check(backend, cwd))

    if errors:
        print("Backend smoke check failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("Backend smoke check passed")


if __name__ == "__main__":
    main()
