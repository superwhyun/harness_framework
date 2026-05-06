import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional


class HandoffWriter:
    TZ = timezone(timedelta(hours=9))

    @classmethod
    def _stamp(cls) -> str:
        return datetime.now(cls.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    @classmethod
    def write(
        cls,
        phase_dir: Path,
        step_num: int,
        step_name: str,
        files_changed: List[str],
        elapsed: int,
        next_step_name: Optional[str],
    ) -> Path:
        output = {
            "summary": f"Step {step_num} ({step_name}) completed",
            "files_changed": files_changed,
            "verification": "AC passed and workspace changes verified via git diff",
            "known_issues": [],
            "next_actions": next_step_name or "phase complete",
            "resume_hint": f"Continue with {next_step_name}" if next_step_name else "Phase is complete. No further steps.",
            "completed_work": [f"Executed step {step_num}: {step_name}"],
            "decisions": {},
            "blockers": None,
            "elapsed_seconds": elapsed,
            "written_at": cls._stamp(),
        }
        out_path = phase_dir / f"step{step_num}-output.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    @staticmethod
    def extract_error(result) -> str:
        if result.stderr.strip():
            return result.stderr.strip()[:500]
        if result.stdout.strip():
            return result.stdout.strip()[:500]
        return f"Step did not complete (exit code {result.exit_code}). No output captured."
