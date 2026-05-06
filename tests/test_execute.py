"""
harness/executor.py 리팩터링 안전망 테스트.
리팩터링 후에도 StepExecutor의 핵심 로직이 정상 작동하는지 검증한다.
"""

import json
import os
import subprocess
import sys
import threading
import time
import types
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# harness 패키지를 찾기 위해 최상위 경로 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.executor import StepExecutor, progress_indicator
from harness.prompt_builder import PromptBuilder
from harness.workspace import WorkspaceSnapshot
from harness.backends.base import BackendResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_project(tmp_path):
    """phases/, CLAUDE.md, docs/ 를 갖춘 임시 프로젝트 구조."""
    phases_dir = tmp_path / "phases"
    phases_dir.mkdir()

    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Shared Rules\n- shared rule")

    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Claude Rules\n- claude rule")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "arch.md").write_text("# Architecture\nSome content")
    (docs_dir / "guide.md").write_text("# Guide\nAnother doc")

    return tmp_path


@pytest.fixture
def phase_dir(tmp_project):
    """step 3개를 가진 phase 디렉토리."""
    d = tmp_project / "phases" / "0-mvp"
    d.mkdir()

    index = {
        "project": "TestProject",
        "phase": "mvp",
        "steps": [
            {"step": 0, "name": "setup", "status": "completed", "summary": "프로젝트 초기화 완료"},
            {"step": 1, "name": "core", "status": "completed", "summary": "핵심 로직 구현"},
            {"step": 2, "name": "ui", "status": "pending"},
        ],
    }
    (d / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    (d / "step2.md").write_text("# Step 2: UI\n\nUI를 구현하세요.")

    return d


@pytest.fixture
def top_index(tmp_project):
    """phases/index.json (top-level)."""
    top = {
        "phases": [
            {"dir": "0-mvp", "status": "pending"},
            {"dir": "1-polish", "status": "pending"},
        ]
    }
    p = tmp_project / "phases" / "index.json"
    p.write_text(json.dumps(top, indent=2))
    return p


@pytest.fixture
def executor(tmp_project, phase_dir):
    """테스트용 StepExecutor 인스턴스."""
    inst = StepExecutor(tmp_project, "0-mvp")
    # 내부 경로를 tmp_project 기준으로 재설정
    inst._root = str(tmp_project)
    inst._phases_dir = tmp_project / "phases"
    inst._phase_dir = phase_dir
    inst._phase_dir_name = "0-mvp"
    inst._index_file = phase_dir / "index.json"
    inst._top_index_file = tmp_project / "phases" / "index.json"
    return inst


# ---------------------------------------------------------------------------
# _stamp
# ---------------------------------------------------------------------------

class TestStamp:
    def test_returns_kst_timestamp(self, executor):
        result = executor._stamp()
        assert "+0900" in result

    def test_format_is_iso(self, executor):
        result = executor._stamp()
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%S%z")
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# _read_json / _write_json
# ---------------------------------------------------------------------------

class TestJsonHelpers:
    def test_roundtrip(self, tmp_path):
        data = {"key": "값", "nested": [1, 2, 3]}
        p = tmp_path / "test.json"
        StepExecutor._write_json(p, data)
        loaded = StepExecutor._read_json(p)
        assert loaded == data


# ---------------------------------------------------------------------------
# _load_guardrails
# ---------------------------------------------------------------------------

class TestLoadGuardrails:
    def test_loads_agents_md_and_docs(self, executor, tmp_project):
        result = PromptBuilder.load_guardrails(
            Path(tmp_project), Path(tmp_project), executor._backend.guardrail_files
        )
        assert "# Shared Rules" in result
        assert "shared rule" in result
        assert "# Architecture" in result
        assert "# Guide" in result

    def test_backend_guardrails(self, executor, tmp_project):
        # Claude 백엔드의 경우 CLAUDE.md를 로드해야 함
        result = PromptBuilder.load_guardrails(
            Path(tmp_project), Path(tmp_project), executor._backend.guardrail_files
        )
        assert "# Claude Rules" in result


# ---------------------------------------------------------------------------
# _build_step_context
# ---------------------------------------------------------------------------

class TestBuildStepContext:
    def test_includes_completed_with_summary(self, phase_dir):
        index = json.loads((phase_dir / "index.json").read_text())
        result = PromptBuilder.build_step_context(index)
        assert "Step 0 (setup): 프로젝트 초기화 완료" in result
        assert "Step 1 (core): 핵심 로직 구현" in result


# ---------------------------------------------------------------------------
# workspace snapshots
# ---------------------------------------------------------------------------

class TestWorkspaceSnapshots:
    def test_diff_workspace_snapshots_detects_changes(self):
        before = {"a.txt": "one", "b.txt": "two"}
        after = {"b.txt": "changed", "c.txt": "three"}
        result = WorkspaceSnapshot.diff(before, after)
        assert sorted(result) == ["a.txt", "b.txt", "c.txt"]


# ---------------------------------------------------------------------------
# _update_top_index (if exists in refactored version)
# ---------------------------------------------------------------------------
# Note: In refactored version, some internal methods might have changed.
# We focus on the core StepExecutor functionality.

def test_executor_initialization(tmp_project, phase_dir):
    executor = StepExecutor(tmp_project, "0-mvp")
    assert executor._project == "TestProject"
    assert executor._phase_name == "mvp"
    assert executor._total == 3
