import subprocess
from typing import List
from .base import AgentBackend, BackendResult
from ..safety import SafetyFilter

class GenericCommandBackend(AgentBackend):
    def __init__(self, name: str, command_template: List[str], guardrail_files: List[str]):
        self.name = name
        self._command_template = command_template
        self.guardrail_files = guardrail_files

    @staticmethod
    def _render_command(command_template: List[str], prompt: str) -> List[str]:
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
        block_reason = SafetyFilter.check_command(command)
        if block_reason:
            return BackendResult(
                backend=self.name,
                command=command,
                exit_code=1,
                stdout="",
                stderr=block_reason,
            )
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
