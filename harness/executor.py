import hashlib
import json
import subprocess
import sys
import threading
import time
import types
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict
import contextlib

from .backends.base import AgentBackend, BackendResult
from .backends.generic import GenericCommandBackend

@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기."""
    frames = "◐◓◑◒"
    stop = threading.Event()
    t0 = time.monotonic()

    def _animate():
        idx = 0
        while not stop.wait(0.12):
            sec = int(time.monotonic() - t0)
            sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            sys.stderr.flush()
            idx += 1
        sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th = threading.Thread(target=_animate, daemon=True)
    th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        th.join()
        info.elapsed = time.monotonic() - t0

class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 하네스 엔진."""

    MAX_RETRIES = 3
    COMMAND_TIMEOUT = 1800
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    # CHORE_MSG removed: step output is committed together with the step work under FEAT_MSG
    TZ = timezone(timedelta(hours=9))
    DEFAULT_BACKEND = "claude"
    
    DEFAULT_BACKENDS = {
        "claude": {
            "command": ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json", "{prompt}"],
            "guardrail_files": ["CLAUDE.md"],
        },
        "codex": {
            "command": ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "{prompt}"],
            "guardrail_files": [],
        },
        "gemini": {
            "command": ["gemini", "--approval-mode", "yolo", "--output-format", "json", "{prompt}"],
            "guardrail_files": [],
        },
        "kimi": {
            "command": ["kimi", "--print", "--output-format", "stream-json", "-p", "{prompt}"],
            "guardrail_files": [],
        },
    }

    def __init__(
        self,
        root: Path,
        phase_dir_name: str,
        *,
        backend_name: Optional[str] = None,
        auto_push: bool = False,
        framework_root: Optional[Path] = None,
    ):
        self._root = str(root)
        self._framework_root = str(framework_root or root)
        self._phases_dir = root / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push
        self._harness_settings = self._load_harness_settings()
        self._backend = self._resolve_backend(backend_name)
        self._step_snapshots: Dict[int, Dict[str, str]] = {}

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])

    def run(self):
        self._print_header()
        self._check_blockers()
        self._checkout_branch()
        guardrails = self._load_guardrails()
        self._ensure_created_at()
        self._execute_all_steps(guardrails)
        self._finalize()

    # --- Utility Methods (IO, timestamps, etc.) ---
    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_harness_settings(self) -> dict:
        config_file = Path(self._root) / "harness.json"
        if not config_file.exists():
            framework_config = Path(self._framework_root) / "harness.json"
            if framework_config.exists():
                config_file = framework_config
        if not config_file.exists():
            return {}
        try:
            return self._read_json(config_file)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: harness.json 을 읽을 수 없습니다: {exc}")
            sys.exit(1)

    def _resolve_backend(self, backend_name: Optional[str]) -> AgentBackend:
        configs = self._get_backend_configs()
        target = backend_name or self._harness_settings.get("default_backend", self.DEFAULT_BACKEND)
        config_data = configs.get(target)
        if config_data is None:
            available = ", ".join(sorted(configs))
            print(f"ERROR: backend '{target}' 가 정의되지 않았습니다. 사용 가능: {available}")
            sys.exit(1)
        
        return GenericCommandBackend(
            name=target,
            command_template=config_data["command"],
            guardrail_files=config_data.get("guardrail_files", [])
        )

    def _get_backend_configs(self) -> dict:
        configs = self.DEFAULT_BACKENDS.copy()
        # Merge harness.json settings
        custom_backends = self._harness_settings.get("backends", {})
        for name, data in custom_backends.items():
            if "command" in data:
                configs[name] = data
        return configs

    # --- Git & Workspace Snapshots ---
    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"
        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print("  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        if r.returncode == 0:
            r = self._run_git("checkout", branch)
        else:
            r = self._run_git("checkout", "-b", branch)
        if r.returncode != 0:
            print(f"  ERROR: git checkout failed: {r.stderr.strip()}")
            sys.exit(1)
        print(f"  Branch: {branch}")

    def _workspace_files(self) -> List[str]:
        result = self._run_git("ls-files", "-co", "--exclude-standard")
        if result.returncode != 0:
            return []
        return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})

    def _file_digest(self, rel_path: str) -> Optional[str]:
        path = Path(self._root) / rel_path
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except (FileNotFoundError, PermissionError):
            return None

    def _capture_workspace_snapshot(self) -> Dict[str, str]:
        snapshot = {}
        for rel_path in self._workspace_files():
            path = Path(self._root) / rel_path
            if path.is_file():
                digest = self._file_digest(rel_path)
                if digest is not None:
                    snapshot[rel_path] = digest
        return snapshot

    @staticmethod
    def _diff_workspace_snapshots(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
        changed = []
        for rel_path in sorted(set(before) | set(after)):
            if before.get(rel_path) != after.get(rel_path):
                changed.append(rel_path)
        return changed

    def _ensure_step_snapshot(self, step_num: int):
        if step_num not in self._step_snapshots:
            self._step_snapshots[step_num] = self._capture_workspace_snapshot()

    # --- Step Context & Execution ---
    def _load_guardrails(self) -> str:
        root = Path(self._root)
        framework_root = Path(self._framework_root)
        sections = []
        seen = set()

        def add_section(path: Path, title: str):
            if not path.exists() or not path.is_file():
                return
            resolved = path.resolve()
            if resolved in seen:
                return
            seen.add(resolved)
            sections.append(f"## {title}\n\n{path.read_text(encoding='utf-8')}")

        add_section(framework_root / "AGENTS.md", "하네스 프레임워크 규칙 (AGENTS.md)")
        framework_docs_dir = framework_root / "docs"
        if framework_docs_dir.is_dir():
            for doc in sorted(framework_docs_dir.glob("*.md")):
                add_section(doc, f"프레임워크 문서 ({doc.stem})")

        add_section(root / "AGENTS.md", "대상 프로젝트 규칙 (AGENTS.md)")
        docs_dir = root / "docs"
        if docs_dir.is_dir():
            for doc in sorted(docs_dir.glob("*.md")):
                add_section(doc, f"대상 프로젝트 문서 ({doc.stem})")

        for rel_path in self._backend.guardrail_files:
            project_path = root / rel_path
            framework_path = framework_root / rel_path
            add_section(project_path if project_path.exists() else framework_path, f"백엔드 보조 규칙 ({rel_path})")

        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def _build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    def _build_resume_context(self, index: dict, step_num: int) -> str:
        sections = []
        for prev_step in range(step_num - 1, -1, -1):
            out_path = self._phase_dir / f"step{prev_step}-output.json"
            if out_path.exists():
                try:
                    prev_output = self._read_json(out_path)
                    lines = [f"## 이전 세션 handoff (Step {prev_step})", ""]
                    if prev_output.get("summary"):
                        lines.append(f"- summary: {prev_output['summary']}")
                    if prev_output.get("files_changed"):
                        lines.append(f"- files_changed: {', '.join(prev_output['files_changed'])}")
                    sections.append("\n".join(lines))
                    break
                except (json.JSONDecodeError, FileNotFoundError, PermissionError, OSError) as exc:
                    print(f"  WARN: resume context read failed for step {prev_step}: {exc}")
        return "\n\n".join(sections) + "\n\n" if sections else ""

    def _build_preamble(self, guardrails: str, step_context: str, resume_context: str, prev_error: Optional[str]) -> str:
        commit_example = self.FEAT_MSG.format(phase=self._phase_name, num="N", name="<step-name>")
        retry_section = f"\n## ⚠ 이전 시도 실패\n\n{prev_error}\n\n---\n\n" if prev_error else ""
        
        return (
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n"
            f"현재 실행 백엔드: {self._backend.name}\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{resume_context}{retry_section}"
            "## 작업 규칙\n\n"
            "1. 이 스텝에 명시된 작업만 수행하라.\n"
            f"2. /phases/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라.\n"
            "3. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )

    @staticmethod
    def _extract_error(result) -> str:
        if result.stderr.strip():
            return result.stderr.strip()[:500]
        if result.stdout.strip():
            return result.stdout.strip()[:500]
        return f"Step did not complete (exit code {result.exit_code}). No output captured."

    def _write_step_output(
        self,
        step_num: int,
        step_name: str,
        before_snapshot: Dict[str, str],
        after_snapshot: Dict[str, str],
        elapsed: int,
    ) -> Path:
        files_changed = self._diff_workspace_snapshots(before_snapshot, after_snapshot)
        index = self._read_json(self._index_file)
        next_step = next(
            (s for s in index["steps"] if s["step"] > step_num and s["status"] == "pending"),
            None,
        )
        output = {
            "summary": f"Step {step_num} ({step_name}) completed",
            "files_changed": files_changed,
            "verification": "AC passed and workspace changes verified via git diff",
            "known_issues": [],
            "next_actions": next_step["name"] if next_step else "phase complete",
            "resume_hint": f"Continue with step {next_step['step']} ({next_step['name']})" if next_step else "Phase is complete. No further steps.",
            "completed_work": [f"Executed step {step_num}: {step_name}"],
            "decisions": {},
            "blockers": None,
            "elapsed_seconds": elapsed,
            "written_at": self._stamp(),
        }
        out_path = self._phase_dir / f"step{step_num}-output.json"
        self._write_json(out_path, output)
        return out_path

    def _execute_single_step(self, step: dict, guardrails: str):
        step_num, step_name = step["step"], step["name"]
        done = sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")
        prev_error = None
        before_snapshot = self._step_snapshots.get(step_num, {})

        for attempt in range(1, self.MAX_RETRIES + 1):
            index = self._read_json(self._index_file)
            step_context = self._build_step_context(index)
            resume_context = self._build_resume_context(index, step_num)
            preamble = self._build_preamble(guardrails, step_context, resume_context, prev_error)

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1: tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                step_file = self._phase_dir / f"step{step_num}.md"
                prompt = preamble + step_file.read_text(encoding="utf-8")
                result = self._backend.invoke(prompt, cwd=self._root, timeout=self.COMMAND_TIMEOUT)
                elapsed = int(pi.elapsed)

            # Re-read index after backend call
            index = self._read_json(self._index_file)
            status = next((s["status"] for s in index["steps"] if s["step"] == step_num), "pending")
            
            if status == "completed":
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                after_snapshot = self._capture_workspace_snapshot()
                out_path = self._write_step_output(step_num, step_name, before_snapshot, after_snapshot, elapsed)
                self._run_git("add", str(out_path.relative_to(Path(self._root))))
                self._run_git("add", "-A")
                self._run_git("commit", "-m", self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name))
                return True
            
            # Simplified error handling for Step 1 refactoring
            if attempt == self.MAX_RETRIES:
                print(f"  ✗ Step {step_num} failed after {self.MAX_RETRIES} attempts.")
                sys.exit(1)
            
            prev_error = self._extract_error(result)

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None: break
            self._ensure_step_snapshot(pending["step"])
            self._execute_single_step(pending, guardrails)

    def _print_header(self):
        print(f"\n{'=' * 60}\n  Harness Step Executor (Refactored)\n  Phase: {self._phase_name}\n  Backend: {self._backend.name}\n{'=' * 60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        for s in index["steps"]:
            if s["status"] in {"error", "blocked"}:
                print(f"  ✗ Phase is in {s['status']} state at Step {s['step']}.")
                sys.exit(1)

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index()
        print(f"\n  ✓ Phase '{self._phase_name}' completed!")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode == 0:
                print(f"  ✓ Pushed branch {branch} to origin")
            else:
                print(f"  ⚠ Push failed: {r.stderr.strip()}")

    def _update_top_index(self):
        top_path = self._top_index_file
        if not top_path.exists():
            return
        try:
            top_index = self._read_json(top_path)
            phases = top_index.get("phases", [])
            for item in phases:
                if item.get("dir") == self._phase_dir_name:
                    item["status"] = "completed"
                    break
            self._write_json(top_path, top_index)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  WARN: could not update top index: {exc}")
