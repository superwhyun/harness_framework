import subprocess
import sys
from pathlib import Path


class GitManager:
    def __init__(self, root: str):
        self._root = root

    def run(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    def current_branch(self) -> str:
        r = self.run("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print("  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            sys.exit(1)
        return r.stdout.strip()

    def checkout(self, branch: str) -> None:
        if self.current_branch() == branch:
            return
        r = self.run("rev-parse", "--verify", branch)
        if r.returncode == 0:
            r = self.run("checkout", branch)
        else:
            r = self.run("checkout", "-b", branch)
        if r.returncode != 0:
            print(f"  ERROR: git checkout failed: {r.stderr.strip()}")
            sys.exit(1)
        print(f"  Branch: {branch}")

    def commit_all(self, message: str) -> None:
        self.run("add", "-A")
        self.run("commit", "-m", message)

    def add(self, path: str) -> None:
        self.run("add", path)

    def push(self, branch: str) -> bool:
        r = self.run("push", "-u", "origin", branch)
        if r.returncode == 0:
            print(f"  ✓ Pushed branch {branch} to origin")
            return True
        else:
            print(f"  ⚠ Push failed: {r.stderr.strip()}")
            return False
