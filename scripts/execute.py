#!/usr/bin/env python3
"""
Harness Step Executor — phase 내 step을 순차 실행하고 자가 교정한다.

Usage:
    python3 scripts/execute.py <phase-dir> [--backend <name>] [--push]
"""

import argparse
import contextlib
import json
import subprocess
import sys
import threading
import time
import types
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다."""
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


@dataclass(frozen=True)
class BackendConfig:
    name: str
    command: list[str]
    guardrail_files: list[str]


@dataclass(frozen=True)
class BackendResult:
    backend: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


class CommandBackend:
    def __init__(self, config: BackendConfig):
        self.name = config.name
        self._command_template = config.command
        self.guardrail_files = config.guardrail_files

    @staticmethod
    def _render_command(command_template: list[str], prompt: str) -> list[str]:
        rendered = []
        replaced = False
        for arg in command_template:
            if "{prompt}" in arg:
                rendered.append(arg.replace("{prompt}", prompt))
                replaced = True
            else:
                rendered.append(arg)
        if not replaced:
            rendered.append(prompt)
        return rendered

    def invoke(self, prompt: str, *, cwd: str, timeout: int) -> BackendResult:
        command = self._render_command(self._command_template, prompt)
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return BackendResult(
            backend=self.name,
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )


class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 하네스."""

    MAX_RETRIES = 3
    COMMAND_TIMEOUT = 1800
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
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

    def __init__(self, phase_dir_name: str, *, backend_name: Optional[str] = None, auto_push: bool = False):
        self._root = str(ROOT)
        self._phases_dir = ROOT / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push
        self._harness_settings = self._load_harness_settings()
        self._backend = self._resolve_backend(backend_name)

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

    # --- timestamps ---

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- JSON I/O ---

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- harness settings ---

    def _load_harness_settings(self) -> dict:
        config_file = Path(self._root) / "harness.json"
        if not config_file.exists():
            return {}
        try:
            return self._read_json(config_file)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: harness.json 을 읽을 수 없습니다: {exc}")
            sys.exit(1)

    @staticmethod
    def _normalize_str_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []

    def _backend_configs(self) -> dict[str, BackendConfig]:
        configs = {
            name: BackendConfig(
                name=name,
                command=list(data["command"]),
                guardrail_files=list(data.get("guardrail_files", [])),
            )
            for name, data in self.DEFAULT_BACKENDS.items()
        }

        for name, data in self._harness_settings.get("backends", {}).items():
            command = data.get("command")
            if not isinstance(command, list) or not all(isinstance(arg, str) for arg in command):
                print(f"ERROR: harness.json backends.{name}.command 는 문자열 배열이어야 합니다.")
                sys.exit(1)
            configs[name] = BackendConfig(
                name=name,
                command=list(command),
                guardrail_files=self._normalize_str_list(data.get("guardrail_files", [])),
            )
        return configs

    def _resolve_backend(self, backend_name: Optional[str]) -> CommandBackend:
        configs = self._backend_configs()
        target = backend_name or self._harness_settings.get("default_backend", self.DEFAULT_BACKEND)
        config = configs.get(target)
        if config is None:
            available = ", ".join(sorted(configs))
            print(f"ERROR: backend '{target}' 가 정의되지 않았습니다. 사용 가능: {available}")
            sys.exit(1)
        return CommandBackend(config)

    # --- git ---

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print("  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        r = self._run_git("checkout", branch) if r.returncode == 0 else self._run_git("checkout", "-b", branch)

        if r.returncode != 0:
            print(f"  ERROR: 브랜치 '{branch}' checkout 실패.")
            print(f"  {r.stderr.strip()}")
            print("  Hint: 변경사항을 stash하거나 commit한 후 다시 시도하세요.")
            sys.exit(1)

        print(f"  Branch: {branch}")

    def _git_state(self) -> dict:
        branch_result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        status_result = self._run_git("status", "--short")

        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        status_lines = status_result.stdout.splitlines() if status_result.returncode == 0 else []
        files_changed = []
        for line in status_lines:
            if not line.strip():
                continue
            path_text = line[3:].strip() if len(line) > 3 else line.strip()
            if " -> " in path_text:
                path_text = path_text.split(" -> ")[-1].strip()
            files_changed.append(path_text)

        return {
            "branch": branch,
            "status_lines": status_lines,
            "files_changed": files_changed,
        }

    def _commit_step(self, step_num: int, step_name: str):
        output_rel = f"phases/{self._phase_dir_name}/step{step_num}-output.json"
        index_rel = f"phases/{self._phase_dir_name}/index.json"

        self._run_git("add", "-A")
        self._run_git("reset", "HEAD", "--", output_rel)
        self._run_git("reset", "HEAD", "--", index_rel)

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  Commit: {msg}")
            else:
                print(f"  WARN: 코드 커밋 실패: {r.stderr.strip()}")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
            r = self._run_git("commit", "-m", msg)
            if r.returncode != 0:
                print(f"  WARN: housekeeping 커밋 실패: {r.stderr.strip()}")

    # --- top-level index ---

    def _update_top_index(self, status: str):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts = self._stamp()
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                phase["status"] = status
                ts_key = {"completed": "completed_at", "error": "failed_at", "blocked": "blocked_at"}.get(status)
                if ts_key:
                    phase[ts_key] = ts
                break
        self._write_json(self._top_index_file, top)

    # --- guardrails & context ---

    def _load_guardrails(self) -> str:
        root = Path(getattr(self, "_root", str(ROOT)))
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

        add_section(root / "AGENTS.md", "프로젝트 규칙 (AGENTS.md)")

        docs_dir = root / "docs"
        if docs_dir.is_dir():
            for doc in sorted(docs_dir.glob("*.md")):
                add_section(doc, doc.stem)

        backend = getattr(self, "_backend", None)
        backend_guardrails = getattr(backend, "guardrail_files", [])
        for rel_path in backend_guardrails:
            add_section(root / rel_path, f"백엔드 보조 규칙 ({rel_path})")

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

    def _read_step_output(self, step_num: int) -> Optional[dict]:
        out_path = self._phase_dir / f"step{step_num}-output.json"
        if not out_path.exists():
            return None
        try:
            return self._read_json(out_path)
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _format_resume_section(title: str, payload: dict) -> str:
        lines = [f"## {title}", ""]
        if payload.get("status"):
            lines.append(f"- status: {payload['status']}")
        if payload.get("summary"):
            lines.append(f"- summary: {payload['summary']}")

        files_changed = payload.get("files_changed") or []
        if files_changed:
            lines.append(f"- files_changed: {', '.join(files_changed)}")

        next_actions = payload.get("next_actions") or []
        if next_actions:
            lines.append(f"- next_actions: {' | '.join(next_actions)}")

        known_issues = payload.get("known_issues") or []
        if known_issues:
            lines.append(f"- known_issues: {' | '.join(known_issues)}")

        resume_hint = payload.get("resume_hint") or []
        if resume_hint:
            lines.append(f"- resume_hint: {', '.join(resume_hint)}")

        return "\n".join(lines)

    def _build_resume_context(self, index: dict, step_num: int) -> str:
        sections = []

        current_attempt = self._read_step_output(step_num)
        if current_attempt and current_attempt.get("status") in {"error", "blocked", "pending"}:
            sections.append(self._format_resume_section("현재 Step 이전 시도", current_attempt))

        for prev_step in range(step_num - 1, -1, -1):
            prev_output = self._read_step_output(prev_step)
            if prev_output is not None:
                sections.append(self._format_resume_section("이전 세션 handoff", prev_output))
                break

        if not sections:
            return ""
        return "\n\n".join(sections) + "\n\n"

    def _build_preamble(
        self,
        guardrails: str,
        step_context: str,
        resume_context: str = "",
        prev_error: Optional[str] = None,
    ) -> str:
        commit_example = self.FEAT_MSG.format(
            phase=self._phase_name,
            num="N",
            name="<step-name>",
        )
        retry_section = ""
        if prev_error:
            retry_section = (
                "\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n"
                f"{prev_error}\n\n---\n\n"
            )
        return (
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n"
            f"현재 실행 백엔드: {self._backend.name}\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{resume_context}{retry_section}"
            "## 작업 규칙\n\n"
            "1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
            "2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
            "3. 기존 테스트를 깨뜨리지 마라.\n"
            "4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
            f"5. /phases/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라:\n"
            "   - AC 통과 → \"completed\" 와 함께 아래 handoff 필드를 가능한 한 채워라:\n"
            "     \"summary\", \"completed_work\", \"files_changed\", \"decisions\", \"verification\", "
            "\"known_issues\", \"next_actions\", \"resume_hint\"\n"
            f"   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → \"error\", \"error_message\" 를 기록하고 "
            "\"known_issues\", \"next_actions\", \"resume_hint\" 를 남겨라\n"
            "   - 사용자 개입이 필요한 경우 → \"blocked\", \"blocked_reason\" 을 기록하고 "
            "\"blockers\", \"next_actions\", \"resume_hint\" 를 남긴 뒤 즉시 중단하라\n"
            "6. handoff 필드는 다음 세션의 다른 AI 툴이 읽을 수 있게 간결하고 구체적으로 작성하라.\n"
            "7. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )

    def _step_record(self, step_num: int, index: Optional[dict] = None) -> dict:
        index = index or self._read_json(self._index_file)
        for step in index["steps"]:
            if step["step"] == step_num:
                return step
        return {"step": step_num, "status": "pending"}

    def _build_step_output(self, step: dict, result: BackendResult, attempt: int) -> dict:
        index = self._read_json(self._index_file)
        record = self._step_record(step["step"], index)
        git_state = self._git_state()

        files_changed = self._normalize_str_list(record.get("files_changed"))
        for path in git_state["files_changed"]:
            if path not in files_changed:
                files_changed.append(path)

        blockers = self._normalize_str_list(record.get("blockers"))
        blocked_reason = record.get("blocked_reason")
        if blocked_reason and blocked_reason not in blockers:
            blockers.insert(0, blocked_reason)

        return {
            "step": step["step"],
            "name": step["name"],
            "backend": result.backend,
            "attempt": attempt,
            "timestamp": self._stamp(),
            "command": result.command,
            "exitCode": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status": record.get("status", "pending"),
            "summary": record.get("summary", ""),
            "completed_work": self._normalize_str_list(record.get("completed_work")),
            "files_changed": files_changed,
            "decisions": self._normalize_str_list(record.get("decisions")),
            "verification": record.get("verification", {}),
            "known_issues": self._normalize_str_list(record.get("known_issues")),
            "next_actions": self._normalize_str_list(record.get("next_actions")),
            "resume_hint": self._normalize_str_list(record.get("resume_hint")),
            "blockers": blockers,
            "error_message": record.get("error_message", ""),
            "blocked_reason": blocked_reason or "",
            "git": git_state,
        }

    # --- backend invocation ---

    def _invoke_backend(self, step: dict, preamble: str, attempt: int = 1) -> dict:
        step_num, step_name = step["step"], step["name"]
        step_file = self._phase_dir / f"step{step_num}.md"

        if not step_file.exists():
            print(f"  ERROR: {step_file} not found")
            sys.exit(1)

        prompt = preamble + step_file.read_text(encoding="utf-8")
        result = self._backend.invoke(prompt, cwd=self._root, timeout=self.COMMAND_TIMEOUT)

        if result.exit_code != 0:
            print(f"\n  WARN: {self._backend.name} 가 비정상 종료됨 (code {result.exit_code})")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")

        output = self._build_step_output(step, result, attempt)
        out_path = self._phase_dir / f"step{step_num}-output.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output

    # --- 헤더 & 검증 ---

    def _print_header(self):
        print(f"\n{'=' * 60}")
        print("  Harness Step Executor")
        print(f"  Phase: {self._phase_name} | Steps: {self._total}")
        print(f"  Backend: {self._backend.name}")
        if self._auto_push:
            print("  Auto-push: enabled")
        print(f"{'=' * 60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        for s in reversed(index["steps"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print("  Fix and reset status to 'pending' to retry.")
                sys.exit(1)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print("  Resolve and reset status to 'pending' to retry.")
                sys.exit(2)
            if s["status"] != "pending":
                break

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    # --- 실행 루프 ---

    def _execute_single_step(self, step: dict, guardrails: str) -> bool:
        """단일 step 실행 (재시도 포함). 완료되면 True, 실패/차단이면 False."""
        step_num, step_name = step["step"], step["name"]
        done = sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")
        prev_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            index = self._read_json(self._index_file)
            step_context = self._build_step_context(index)
            resume_context = self._build_resume_context(index, step_num)
            preamble = self._build_preamble(guardrails, step_context, resume_context, prev_error)

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1:
                tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                self._invoke_backend(step, preamble, attempt)
                elapsed = int(pi.elapsed)

            index = self._read_json(self._index_file)
            status = next((s.get("status", "pending") for s in index["steps"] if s["step"] == step_num), "pending")
            ts = self._stamp()

            if status == "completed":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["completed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                return True

            if status == "blocked":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["blocked_at"] = ts
                self._write_json(self._index_file, index)
                reason = next((s.get("blocked_reason", "") for s in index["steps"] if s["step"] == step_num), "")
                print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
                print(f"    Reason: {reason}")
                self._update_top_index("blocked")
                sys.exit(2)

            err_msg = next(
                (s.get("error_message", "Step did not update status") for s in index["steps"] if s["step"] == step_num),
                "Step did not update status",
            )

            if attempt < self.MAX_RETRIES:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "pending"
                        s.pop("error_message", None)
                self._write_json(self._index_file, index)
                prev_error = err_msg
                print(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")
            else:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "error"
                        s["error_message"] = f"[{self.MAX_RETRIES}회 시도 후 실패] {err_msg}"
                        s["failed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  ✗ Step {step_num}: {step_name} failed after {self.MAX_RETRIES} attempts [{elapsed}s]")
                print(f"    Error: {err_msg}")
                self._update_top_index("error")
                sys.exit(1)

        return False  # unreachable

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None:
                print("\n  All steps completed!")
                return

            step_num = pending["step"]
            for s in index["steps"]:
                if s["step"] == step_num and "started_at" not in s:
                    s["started_at"] = self._stamp()
                    self._write_json(self._index_file, index)
                    break

            self._execute_single_step(pending, guardrails)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  ✓ {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
                sys.exit(1)
            print(f"  ✓ Pushed to origin/{branch}")

        print(f"\n{'=' * 60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--backend", help="Backend name from harness.json or built-in defaults")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    args = parser.parse_args()

    StepExecutor(args.phase_dir, backend_name=args.backend, auto_push=args.push).run()


if __name__ == "__main__":
    main()
