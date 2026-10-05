import json
import sys
import threading
import time
import types
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List
import contextlib

from .backends.base import AgentBackend, BackendResult
from .backends.generic import GenericCommandBackend, diagnostic
from .git_manager import GitManager
from .prompt_builder import PromptBuilder
from .manifest import update_project_manifest
from .process import run_command
from .state import write_json


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

    th = threading.Thread(target=_animate, daemon=True) if sys.stderr.isatty() else None
    if th:
        th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        if th:
            th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    MAX_RETRIES = 3
    COMMAND_TIMEOUT = 1800
    FEAT_MSG = "feat({project}/step{num}): {name}"
    TZ = timezone(timedelta(hours=9))
    DEFAULT_BACKEND = "claude"

    # Safe default backends (no dangerous flags)
    # Common guardrail baseline applied to all backends
    _COMMON_GUARDRAILS = ["AGENTS.md"]

    DEFAULT_BACKENDS = {
        "claude": {
            "command": ["claude", "-p", "--permission-mode", "acceptEdits", "--output-format", "json", "{prompt}"],
            "guardrail_files": _COMMON_GUARDRAILS + ["CLAUDE.md"],
        },
        "codex": {
            "command": ["codex", "exec", "--json", "--sandbox", "workspace-write", "{prompt}"],
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
        auto_commit: bool = True,
        framework_root: Optional[Path] = None,
    ):
        if Path(phase_dir_name).name != phase_dir_name or phase_dir_name in {"", ".", ".."}:
            raise ValueError("phase directory must be a single directory name")
        self._root = str(root)
        self._framework_root = str(framework_root or root)
        self._phases_dir = root / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._index_file = self._phase_dir / "index.json"
        self._auto_push = auto_push
        self._auto_commit = auto_commit
        if auto_push and not auto_commit:
            raise ValueError("--push cannot be combined with --no-commit")
        self._harness_settings = self._load_harness_settings()
        self._backend = self._resolve_backend(backend_name)
        self._git = GitManager(self._root)
        self._prompt = PromptBuilder()

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])
        self._validate_index(idx)
        execution = self._harness_settings.get("execution", {})
        if not isinstance(execution, dict):
            raise ValueError("execution must be an object")
        self._max_attempts = execution.get("max_attempts", self.MAX_RETRIES)
        self._timeout = execution.get("timeout_seconds", self.COMMAND_TIMEOUT)
        if any(type(value) is not int or value < 1 for value in (self._max_attempts, self._timeout)):
            raise ValueError("execution max_attempts and timeout_seconds must be positive integers")

    def run(self):
        self._print_header()
        self._check_stop()
        self._check_blockers()
        self._git.current_branch()
        if self._auto_commit:
            self._git.require_clean()
            self._git.checkout(f"feat-{self._phase_name}")
        guardrails = self._prompt.load_guardrails(
            Path(self._root), Path(self._framework_root), self._backend.guardrail_files,
            getattr(self._backend, "instruction_mode", "inline"),
        )
        manifest_context = self._prompt.load_project_manifest(self._phases_dir)
        self._ensure_created_at()
        self._execute_all_steps(guardrails, manifest_context)
        self._finalize()

    @staticmethod
    def _read_json(p: Path) -> dict:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{p} must contain a JSON object")
        return data

    @staticmethod
    def _write_json(p: Path, data: dict):
        write_json(p, data)

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
            guardrail_files=config_data.get("guardrail_files", []),
            instruction_mode=config_data.get("instruction_mode", "inline"),
        )

    def _get_backend_configs(self) -> dict:
        if self._harness_settings.get("dangerous_mode", False):
            configs = self.DANGEROUS_BACKENDS.copy()
        else:
            configs = self.DEFAULT_BACKENDS.copy()
        configs = {name: {**data, "instruction_mode": "native"} for name, data in configs.items()}
        custom_backends = self._harness_settings.get("backends", {})
        if not isinstance(custom_backends, dict):
            raise ValueError("backends must be an object")
        for name, data in custom_backends.items():
            if not isinstance(data, dict):
                raise ValueError(f"backend {name} must be an object")
            configs[name] = {**configs.get(name, {}), **data}
            # A replacement command may not have the built-in CLI's instruction loader.
            if "command" in data and "instruction_mode" not in data:
                configs[name]["instruction_mode"] = "inline"
            if "command" not in configs[name]:
                raise ValueError(f"backend {name} requires command")
        return configs

    @staticmethod
    def _validate_index(index: dict):
        steps = index.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("phase must contain a non-empty steps array")
        ids = [step.get("step") for step in steps if isinstance(step, dict)]
        if len(ids) != len(steps) or any(type(i) is not int or i < 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("step IDs must be unique non-negative integers")
        for step in steps:
            if step.get("status") not in {"pending", "completed", "error", "blocked"}:
                raise ValueError(f"Invalid status for step {step['step']}")
            refs = step.get("depends_on", [])
            if not isinstance(refs, list) or any(type(i) is not int or i not in ids or i == step["step"] for i in refs):
                raise ValueError(f"Invalid depends_on for step {step['step']}")
            checks = step.get("checks", [])
            if not isinstance(checks, list) or any(
                not isinstance(cmd, list) or not cmd or not all(isinstance(arg, str) and arg for arg in cmd)
                for cmd in checks
            ):
                raise ValueError(f"checks for step {step['step']} must be an array of argv arrays")

    def _check_stop(self):
        if (self._phases_dir / "STOP").exists():
            raise RuntimeError("phases/STOP exists. Work is preserved; remove it to resume.")

    def _fail_step(self, step_num: int, message: str, *, blocked: bool = False):
        index = self._read_json(self._index_file)
        step = next(s for s in index["steps"] if s["step"] == step_num)
        step["status"] = "blocked" if blocked else "error"
        step["blocked_reason" if blocked else "error_message"] = message
        step["next_action"] = "Resolve the cause, review existing changes, set this step to pending, then resume (use --no-commit for a dirty tree)."
        index.pop("completed_at", None)
        self._write_json(self._index_file, index)
        raise RuntimeError(f"Step {step_num}: {message}")

    def _run_checks(self, checks: list[list[str]]) -> tuple[list[dict], Optional[str]]:
        evidence = []
        for command in checks:
            self._check_stop()
            try:
                result = run_command(command, cwd=self._root, timeout=self._timeout)
                evidence.append({"command": command, "exit_code": result.returncode,
                                 "output": (result.stderr or result.stdout)[-2000:]})
                if result.returncode:
                    return evidence, f"Check failed: {command!r}\n{evidence[-1]['output']}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                evidence.append({"command": command, "error": str(exc)})
                return evidence, f"Check could not complete: {command!r}: {exc}"
        return evidence, None

    def _execute_single_step(self, step: dict, guardrails: str, manifest_context: str):
        step_num, step_name = step["step"], step["name"]
        checks = step.get("checks", [])
        prev_error = None
        for attempt in range(1, self._max_attempts + 1):
            self._check_stop()
            index = self._read_json(self._index_file)
            self._validate_index(index)
            current_step = next(s for s in index["steps"] if s["step"] == step_num)
            # Evidence belongs to the current attempt, not an earlier failed run.
            current_step.pop("verification", None)
            self._write_json(self._index_file, index)
            preamble = self._prompt.build_preamble(
                project=self._project, phase_name=self._phase_name, phase_dir_name=self._phase_dir_name,
                backend_name=self._backend.name, guardrails=guardrails, manifest_context=manifest_context,
                step_context=self._prompt.build_step_context(index, current_step),
                prev_error=prev_error, feat_msg_template=self.FEAT_MSG,
            )
            prompt = preamble + (self._phase_dir / f"step{step_num}.md").read_text(encoding="utf-8")
            before = self._git.progress_digest()
            tag = f"Step {step_num}: {step_name} (attempt {attempt}/{self._max_attempts})"
            try:
                with progress_indicator(tag) as pi:
                    result = self._backend.invoke(prompt, cwd=self._root, timeout=self._timeout)
            except KeyboardInterrupt:
                self._fail_step(step_num, "Interrupted. Inspect partial changes before resuming.")
            elapsed = round(pi.elapsed, 2)
            updated = self._read_json(self._index_file)
            self._validate_index(updated)
            by_id = {s["step"]: s for s in updated["steps"]}
            # Do not allow a model to weaken gates or skip other work through bookkeeping.
            violations = []
            for old in index["steps"]:
                new = by_id.get(old["step"])
                if new is None:
                    updated["steps"].append(old)
                    violations.append("existing step removed")
                    continue
                for key in ("checks", "depends_on"):
                    if new.get(key, []) != old.get(key, []):
                        new[key] = old.get(key, [])
                        violations.append(f"{key} changed")
                if old["step"] != step_num and new["status"] == "completed" and old["status"] != "completed":
                    new["status"] = old["status"]
                    violations.append("another step marked completed")
            for new in updated["steps"]:
                if new["step"] not in {s["step"] for s in index["steps"]} and new["status"] == "completed":
                    new["status"] = "pending"
                    violations.append("new step marked completed without execution")
            current = next(s for s in updated["steps"] if s["step"] == step_num)
            reported_status = current["status"]
            if reported_status == "completed":
                current["status"] = "pending"  # completion is not durable until gates pass
            current["last_attempt"] = {"attempt": attempt, "at": self._stamp(), "exit_code": result.exit_code, "elapsed_seconds": elapsed}
            self._write_json(self._index_file, updated)
            if violations:
                self._fail_step(step_num, "Invalid progress update: " + ", ".join(sorted(set(violations))))
            if reported_status in {"blocked", "error"}:
                self._fail_step(step_num, current.get("blocked_reason") or current.get("error_message") or "Agent reported failure.",
                                blocked=current["status"] == "blocked")

            error = None
            if result.exit_code:
                error = f"Backend exited {result.exit_code}: {diagnostic(result.stdout, result.stderr)}"
            elif reported_status != "completed":
                error = "Agent ended without completing the step. " + diagnostic(result.stdout, result.stderr)
            elif not isinstance(current.get("summary"), str) or not current["summary"].strip():
                error = "Completed step is missing summary."
            elif checks:
                try:
                    evidence, error = self._run_checks(checks)
                except KeyboardInterrupt:
                    self._fail_step(step_num, "Interrupted during verification. Rerun checks before completing.")
                current["verification"] = {"status": "failed" if error else "passed", "source": "executor", "checks": evidence}
            else:
                verification = current.get("verification", {})
                if not isinstance(verification, dict) or verification.get("status") != "passed" or not isinstance(verification.get("details"), str) or not verification["details"].strip():
                    error = "Completed step needs verification.status=passed and non-empty verification.details, or configured checks."

            if error is None:
                current["status"] = "completed"
                current.pop("error_message", None)
                current.pop("blocked_reason", None)
                current.pop("next_action", None)
                released = self._release_blocked_steps(updated, current)
                if released:
                    current["unblocked_steps"] = released
                self._write_json(self._index_file, updated)
                if self._auto_commit:
                    self._git.commit_all(self.FEAT_MSG.format(project=self._project, num=step_num, name=step_name))
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                return True

            current["status"] = "pending"
            current["last_attempt"]["error"] = error
            self._write_json(self._index_file, updated)
            progressed = self._git.progress_digest() != before
            kind = getattr(result, "failure_kind", None)
            retryable = kind == "transient" or progressed
            if kind in {"configuration", "timeout"} or not retryable or attempt == self._max_attempts:
                self._fail_step(step_num, error)
            prev_error = error
            if kind == "transient":
                time.sleep(min(2 ** attempt, 30))

    def _execute_all_steps(self, guardrails: str, manifest_context: str):
        while True:
            self._check_stop()
            index = self._read_json(self._index_file)
            self._validate_index(index)
            self._check_blockers()
            pending = self._select_next_step(index)
            if pending is None:
                if any(s["status"] != "completed" for s in index["steps"]):
                    raise RuntimeError("Unfinished steps have unresolved dependencies or blockers. Inspect index.json.")
                return
            self._execute_single_step(pending, guardrails, manifest_context)

    def _print_header(self):
        print(f"\n{'=' * 60}\n  Harness Step Executor (Refactored)\n  Phase: {self._phase_name}\n  Backend: {self._backend.name}\n{'=' * 60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        if any(s.get("status") == "error" for s in index["steps"]):
            errored = next(s for s in index["steps"] if s.get("status") == "error")
            print(f"  ✗ Phase is in error state at Step {errored['step']}.")
            sys.exit(1)

        blocked = [s for s in index["steps"] if s.get("status") == "blocked"]
        if blocked and self._pending_blocking_fix(index) is None:
            first_blocked = blocked[0]
            print(f"  ✗ Phase is blocked at Step {first_blocked['step']} and has no pending blocking-fix step.")
            sys.exit(1)

    @staticmethod
    def _pending_blocking_fix(index: dict) -> Optional[dict]:
        completed = {step["step"] for step in index["steps"] if step.get("status") == "completed"}
        for s in index["steps"]:
            if (s.get("status") == "pending" and s.get("kind") == "blocking-fix"
                    and all(ref in completed for ref in s.get("depends_on", []))):
                return s
        return None

    @classmethod
    def _select_next_step(cls, index: dict) -> Optional[dict]:
        blocking_fix = cls._pending_blocking_fix(index)
        if blocking_fix is not None:
            return blocking_fix
        completed = {s["step"] for s in index["steps"] if s.get("status") == "completed"}
        return next((s for s in index["steps"] if s.get("status") == "pending"
                     and all(ref in completed for ref in s.get("depends_on", []))), None)

    @staticmethod
    def _normalize_step_refs(value) -> List[int]:
        if value is None:
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, int)]
        return []

    def _release_blocked_steps(self, index: dict, fixer_step: dict) -> List[int]:
        if fixer_step.get("kind") != "blocking-fix":
            return []

        targets = self._normalize_step_refs(fixer_step.get("unblocks"))
        targets += self._normalize_step_refs(fixer_step.get("unblocks_step"))
        if not targets:
            return []

        released: List[int] = []
        for step in index["steps"]:
            if step.get("step") in targets and step.get("status") == "blocked":
                step["status"] = "pending"
                step["unblocked_by_step"] = fixer_step["step"]
                step.pop("blocked_by_step", None)
                released.append(step["step"])
        return released

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    def _finalize(self):
        index = self._read_json(self._index_file)
        self._validate_index(index)
        if any(s["status"] != "completed" for s in index["steps"]):
            raise RuntimeError("Cannot finalize a phase with unfinished steps.")
        index.setdefault("completed_at", self._stamp())
        self._write_json(self._index_file, index)
        baseline = self._write_phase_baseline(index)
        if baseline:
            update_project_manifest(self._phases_dir, self._phase_dir_name, baseline)
        self._update_top_index()
        if self._auto_commit:
            self._git.commit_all(f"chore({self._project}): finalize {self._phase_name}")
        print(f"\n  ✓ Phase '{self._phase_name}' completed!")
        if self._auto_push:
            self._git.push(f"feat-{self._phase_name}")

    def _write_phase_baseline(self, index: dict) -> Optional[dict]:
        baseline_dir = self._phases_dir / "baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        baseline_path = baseline_dir / f"{self._phase_dir_name}.json"
        if baseline_path.exists():
            return self._read_json(baseline_path)

        module_map_path = self._phase_dir / "module-map.json"
        module_map = {}
        if module_map_path.exists():
            try:
                module_map = self._read_json(module_map_path)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Cannot create baseline from unreadable module-map: {exc}") from exc

        source_module_map = None
        if module_map_path.exists():
            source_module_map = f"phases/{self._phase_dir_name}/module-map.json"

        baseline = {
            "schema_version": 1,
            "project": self._project,
            "phase": self._phase_dir_name,
            "phase_name": self._phase_name,
            "tag": None,
            "source_module_map": source_module_map,
            "modules": module_map.get("modules", []),
            "routes": [],
            "shared_contracts": module_map.get("shared_contracts", []),
            "integration_points": module_map.get("integration_points", []),
            "known_issues": [],
            "completed_steps": [
                {"step": step.get("step"), "name": step.get("name"), "summary": step.get("summary")}
                for step in index.get("steps", [])
                if step.get("status") == "completed"
            ],
            "completed_at": index.get("completed_at"),
            "written_at": self._stamp(),
        }
        self._write_json(baseline_path, baseline)
        return baseline

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
            raise ValueError(f"Could not update top index: {exc}") from exc
