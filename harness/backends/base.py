from dataclasses import dataclass
from typing import Protocol, List, Optional

@dataclass(frozen=True)
class BackendResult:
    backend: str
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    failure_kind: Optional[str] = None

class AgentBackend(Protocol):
    name: str
    guardrail_files: List[str]
    instruction_mode: str

    def invoke(self, prompt: str, *, cwd: str, timeout: int) -> BackendResult:
        ...
