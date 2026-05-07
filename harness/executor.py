import json
import sys
import threading
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict
import contextlib

from .backends.base import AgentBackend, BackendResult
from .backends.generic import GenericCommandBackend
from .git_manager import GitManager
from .workspace import WorkspaceSnapshot
from .prompt_builder import PromptBuilder
from .handoff_writer import HandoffWriter


@contextlib.contextmanager
def progress_indicator(label: str):
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
    MAX_RETRIES = 3
    COMMAND_TIMEOUT = 1800
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    TZ = timezone(timedelta(hours=9))
    DEFAULT_BACKEND = "claude"

    # Safe default backends (no dangerous flags)
    # Common guardrail baseline applied to all backends
    _COMMON_GUARDRAILS = ["AGENTS.md"]

    DEFAULT_BACKENDS = {
        "claude": {
            "command": ["claude", "-p", "--output-format", "json", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS + ["CLAUDE.md"],
        },
        "codex": {
            "command": ["codex", "exec", "--json", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS,
        },
        "gemini": {
            "command": ["gemini", "--output-format", "json", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS + ["GEMINI.md"],
        },
        "kimi": {
            "command": ["kimi", "--output-format", "stream-json", "-p", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS,
        },
    }

    # Dangerous backends (used when harness.json has dangerous_mode: true)
    DANGEROUS_BACKENDS = {
        "claude": {
            "command": ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS + ["CLAUDE.md"],
        },
        "codex": {
            "command": ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS,
        },
        "gemini": {
            "command": ["gemini", "--approval-mode", "yolo", "--output-format", "json", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS + ["GEMINI.md"],
        },
        "kimi": {
            "command": ["kimi", "--print", "--output-format", "stream-json", "-p", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS,
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
        self._git = GitManager(self._root)
        self._workspace = WorkspaceSnapshot(self._root)
        self._prompt = PromptBuilder()

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
        self._git.checkout(f"feat-{self._phase_name}")
        guardrails = self._prompt.load_guardrails(
            Path(self._root), Path(self._framework_root), self._backend.guardrail_files
        )
        self._ensure_created_at()
        self._execute_all_steps(guardrails)
        self._finalize()

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

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
        if self._harness_settings.get("dangerous_mode", False):
            configs = self.DANGEROUS_BACKENDS.copy()
        else:
            configs = self.DEFAULT_BACKENDS.copy()
        custom_backends = self._harness_settings.get("backends", {})
        for name, data in custom_backends.items():
            if "command" in data:
                configs[name] = data
        return configs

    def _execute_single_step(self, step: dict, guardrails: str):
        step_num, step_name = step["step"], step["name"]
        done = sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")
        prev_error = None
        if step_num not in self._step_snapshots:
            self._step_snapshots[step_num] = self._workspace.capture()
        before_snapshot = self._step_snapshots[step_num]

        for attempt in range(1, self.MAX_RETRIES + 1):
            index = self._read_json(self._index_file)
            step_context = self._prompt.build_step_context(index)
            resume_context = self._prompt.build_resume_context(self._phase_dir, step_num)
            preamble = self._prompt.build_preamble(
                project=self._project,
                phase_name=self._phase_name,
                phase_dir_name=self._phase_dir_name,
                backend_name=self._backend.name,
                guardrails=guardrails,
                step_context=step_context,
                resume_context=resume_context,
                prev_error=prev_error,
                feat_msg_template=self.FEAT_MSG,
            )

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1:
                tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                step_file = self._phase_dir / f"step{step_num}.md"
                prompt = preamble + step_file.read_text(encoding="utf-8")
                result = self._backend.invoke(prompt, cwd=self._root, timeout=self.COMMAND_TIMEOUT)
                elapsed = int(pi.elapsed)

            index = self._read_json(self._index_file)
            status = next((s["status"] for s in index["steps"] if s["step"] == step_num), "pending")

            if status == "completed":
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                after_snapshot = self._workspace.capture()
                files_changed = self._workspace.diff(before_snapshot, after_snapshot)
                next_step = next(
                    (s for s in index["steps"] if s["step"] > step_num and s["status"] == "pending"),
                    None,
                )
                out_path = HandoffWriter.write(
                    phase_dir=self._phase_dir,
                    step_num=step_num,
                    step_name=step_name,
                    files_changed=files_changed,
                    elapsed=elapsed,
                    next_step_name=next_step["name"] if next_step else None,
                )
                self._git.add(str(out_path.relative_to(Path(self._root))))
                self._git.commit_all(self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name))
                return True

            if attempt == self.MAX_RETRIES:
                print(f"  ✗ Step {step_num} failed after {self.MAX_RETRIES} attempts.")
                sys.exit(1)

            prev_error = HandoffWriter.extract_error(result)

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None:
                break
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
            self._git.push(f"feat-{self._phase_name}")

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
