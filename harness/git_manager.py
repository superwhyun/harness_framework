import hashlib
import subprocess
import sys
from pathlib import Path


class GitManager:
    def __init__(self, root: str):
        self._root = root

    def run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self._root, capture_output=True, text=True)

    def checked(self, *args) -> subprocess.CompletedProcess:
        result = self.run(*args)
        if result.returncode:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def current_branch(self) -> str:
        r = self.run("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode:
            print("ERROR: Git repository with an initial commit is required.")
            sys.exit(1)
        return r.stdout.strip()

    def require_clean(self) -> None:
        if self.checked("status", "--porcelain").stdout:
            raise RuntimeError(
                "Working tree has existing changes. Review/commit them first, or use --no-commit "
                "to resume without automatic branch/commit/push."
            )

    def checkout(self, branch: str) -> None:
        if self.current_branch() == branch:
            return
        exists = self.run("rev-parse", "--verify", branch).returncode == 0
        result = self.run("checkout", branch) if exists else self.run("checkout", "-b", branch)
        if result.returncode:
            print(f"ERROR: git checkout failed: {result.stderr.strip()}")
            sys.exit(1)
        print(f"  Branch: {branch}")

    def commit_all(self, message: str) -> None:
        self.checked("add", "-A")
        staged = self.run("diff", "--cached", "--quiet")
        if staged.returncode == 0:
            return
        if staged.returncode != 1:
            raise RuntimeError(f"Cannot inspect staged changes: {staged.stderr.strip()}")
        self.checked("commit", "-m", message)

    def add(self, path: str) -> None:
        self.checked("add", "--", path)

    def push(self, branch: str) -> bool:
        self.checked("push", "-u", "origin", branch)
        print(f"  ✓ Pushed branch {branch} to origin")
        return True

    def progress_digest(self) -> str:
        """Hash changed content only; status bookkeeping is not implementation progress."""
        digest = hashlib.sha256()
        diff = self.checked("diff", "--binary", "HEAD", "--", ".", ":(exclude)phases", ":(exclude).harness")
        digest.update(diff.stdout.encode())
        paths = self.checked("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
        for name in sorted(filter(None, paths)):
            if name.startswith(("phases/", ".harness/")):
                continue
            path = Path(self._root) / name
            digest.update(name.encode())
            if path.is_symlink():
                digest.update(str(path.readlink()).encode())
            elif path.is_file():
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(65536), b""):
                        digest.update(chunk)
        return digest.hexdigest()
