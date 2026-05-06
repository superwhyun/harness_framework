import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class WorkspaceSnapshot:
    def __init__(self, root: str):
        self._root = root

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def list_files(self) -> List[str]:
        result = self._run_git("ls-files", "-co", "--exclude-standard")
        if result.returncode != 0:
            return []
        return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})

    def file_digest(self, rel_path: str) -> Optional[str]:
        path = Path(self._root) / rel_path
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except (FileNotFoundError, PermissionError):
            return None

    def capture(self) -> Dict[str, str]:
        snapshot = {}
        for rel_path in self.list_files():
            path = Path(self._root) / rel_path
            if path.is_file():
                digest = self.file_digest(rel_path)
                if digest is not None:
                    snapshot[rel_path] = digest
        return snapshot

    @staticmethod
    def diff(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
        changed = []
        for rel_path in sorted(set(before) | set(after)):
            if before.get(rel_path) != after.get(rel_path):
                changed.append(rel_path)
        return changed
