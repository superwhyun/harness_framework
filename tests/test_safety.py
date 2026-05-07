"""
Tests for harness/safety.py dangerous command filter.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.safety import SafetyFilter


def test_blocks_rm_rf_root():
    reason = SafetyFilter.check_command(["rm", "-rf", "/"])
    assert reason is not None
    assert "rm -rf /" in reason


def test_blocks_git_push_force():
    reason = SafetyFilter.check_command(["git", "push", "--force", "origin", "main"])
    assert reason is not None
    assert "git push --force" in reason


def test_blocks_git_reset_hard():
    reason = SafetyFilter.check_command(["git", "reset", "--hard", "HEAD~1"])
    assert reason is not None
    assert "git reset --hard" in reason


def test_blocks_drop_table():
    reason = SafetyFilter.check_command(["psql", "-c", "DROP TABLE users"])
    assert reason is not None
    assert "DROP TABLE" in reason


def test_allows_safe_rm():
    reason = SafetyFilter.check_command(["rm", "-rf", "build/"])
    assert reason is None


def test_allows_normal_git_push():
    reason = SafetyFilter.check_command(["git", "push", "origin", "main"])
    assert reason is None


def test_allows_normal_commands():
    assert SafetyFilter.check_command(["python3", "scripts/execute.py", "0-mvp"]) is None
    assert SafetyFilter.check_command(["npm", "run", "test"]) is None
    assert SafetyFilter.check_command(["pytest", "tests/"]) is None
