from dataclasses import dataclass
from typing import Protocol, List, Optional

@dataclass(frozen=True)
class BackendResult:
    backend: str
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str

class AgentBackend(Protocol):
    name: str
    guardrail_files: List[str]

    def invoke(self, prompt: str, *, cwd: str, timeout: int) -> BackendResult:
        ...
