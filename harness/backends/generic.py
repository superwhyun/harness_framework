import json
import subprocess
from typing import List

from .base import AgentBackend, BackendResult
from ..process import run_command


def structured_errors(stdout: str) -> list[str]:
    errors = []
    try:
        events = [json.loads(stdout)]
    except ValueError:
        events = []
        for line in stdout.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    for event in events:
        if isinstance(event, dict) and (
            event.get("type") == "turn.completed"
            or (event.get("type") == "result" and event.get("is_error") is False)
        ):
            errors.clear()  # Recovered transport errors do not invalidate a successful turn.
            continue
        if isinstance(event, dict) and (
            event.get("is_error") or event.get("type") in {"error", "turn.failed"}
            or event.get("error")
        ):
            errors.append(str(event.get("error") or event.get("message") or event.get("result") or event))
    return errors


def diagnostic(stdout: str, stderr: str) -> str:
    """Prefer structured CLI errors; keep the useful end of plain output."""
    errors = structured_errors(stdout)
    return "\n".join(errors + ([stderr.strip()] if stderr.strip() else []))[-4000:] or stdout.strip()[-4000:]


class GenericCommandBackend(AgentBackend):
    def __init__(self, name: str, command_template: List[str], guardrail_files: List[str],
                 instruction_mode: str = "inline"):
        if instruction_mode not in {"native", "inline"}:
            raise ValueError("instruction_mode must be native or inline")
        if not isinstance(command_template, list) or not command_template or not all(isinstance(arg, str) and arg for arg in command_template):
            raise ValueError("backend command must be a non-empty string array")
        if not isinstance(guardrail_files, list) or not all(isinstance(path, str) and path for path in guardrail_files):
            raise ValueError("guardrail_files must be a string array")
        self.name = name
        self._command_template = command_template
        self.guardrail_files = guardrail_files
        self.instruction_mode = instruction_mode

    @staticmethod
    def _render_command(command_template: List[str], prompt: str) -> List[str]:
        rendered = [arg.replace("{prompt}", prompt) for arg in command_template]
        if not any("{prompt}" in arg for arg in command_template):
            rendered.append(prompt)
        return rendered

    def invoke(self, prompt: str, *, cwd: str, timeout: int) -> BackendResult:
        command = self._render_command(self._command_template, prompt)
        # Prompt text is data, not a shell command. Tool permissions belong to the CLI.
        try:
            result = run_command(command, cwd=cwd, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            return BackendResult(self.name, command, 124, exc.stdout or "",
                                 f"Timed out after {timeout}s.\n{exc.stderr or ''}", "timeout")
        except OSError as exc:
            return BackendResult(self.name, command, 127, "", str(exc), "configuration")

        exit_code = result.returncode
        # Some CLIs report an agent failure in a successful JSON transport response.
        if structured_errors(result.stdout):
            exit_code = exit_code or 1
        failure_kind = None
        if exit_code:
            detail = diagnostic(result.stdout, result.stderr).lower()
            if any(word in detail for word in (
                "unauthorized", "invalid api key", "authentication", "not logged in",
                "permission denied", "unknown option", "unrecognized argument", "model not found",
            )):
                failure_kind = "configuration"
            elif any(word in detail for word in ("rate limit", "429", "temporarily unavailable", "503", "connection reset")):
                failure_kind = "transient"
            else:
                failure_kind = "process"
        return BackendResult(self.name, command, exit_code, result.stdout, result.stderr, failure_kind)
