import re
from typing import Optional


class SafetyFilter:
    """프레임워크 레벨 위험 명령 필터."""

    DANGEROUS_PATTERNS = [
        (re.compile(r"rm\s+-rf\s+/"), "absolute path recursive deletion (rm -rf /)"),
        (re.compile(r"git\s+push\s+--force"), "force push (git push --force)"),
        (re.compile(r"git\s+reset\s+--hard"), "hard reset (git reset --hard)"),
        (re.compile(r"DROP\s+TABLE", re.IGNORECASE), "SQL table drop (DROP TABLE)"),
        (re.compile(r"mkfs\."), "filesystem formatting (mkfs)"),
        (re.compile(r"dd\s+if="), "raw disk write (dd if=)"),
    ]

    @classmethod
    def check_command(cls, command: list[str]) -> Optional[str]:
        cmd_str = " ".join(command)
        for pattern, reason in cls.DANGEROUS_PATTERNS:
            if pattern.search(cmd_str):
                return f"BLOCKED: 위험한 명령어가 감지되었습니다 — {reason}. 명령: {cmd_str}"
        return None
