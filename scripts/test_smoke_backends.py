import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parent / "smoke_backends.py"
REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_BINARIES = ["claude", "codex", "gemini", "kimi"]


@pytest.mark.skipif(
    not all(shutil.which(binary) for binary in REQUIRED_BINARIES),
    reason="backend CLIs are not installed",
)
def test_backend_help_smoke():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
