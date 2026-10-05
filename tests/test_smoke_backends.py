import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from unittest.mock import patch

from scripts.smoke_backends import run_help_check


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "smoke_backends.py"
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


def test_missing_interpreter_is_reported_without_traceback(tmp_path):
    with patch("scripts.smoke_backends.shutil.which", return_value="/bin/kimi"), patch(
        "scripts.smoke_backends.subprocess.run", side_effect=FileNotFoundError("missing interpreter")
    ):
        assert run_help_check("kimi", tmp_path, skip_unavailable=True) == []
        assert "cannot launch" in run_help_check("kimi", tmp_path)[0]
