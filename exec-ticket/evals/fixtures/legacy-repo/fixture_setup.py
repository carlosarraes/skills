#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).parent.resolve()
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_DATE": "2026-07-23T12:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-07-23T12:00:00+00:00",
}


def git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env=GIT_ENV,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if (ROOT / ".git").exists():
    raise SystemExit("fixture repository is already initialized")

git("init", "-q")
git("config", "user.name", "Fixture")
git("config", "user.email", "fixture@example.invalid")
git("checkout", "-q", "-b", "feature/proj-123")
git("add", ".")
git("commit", "-q", "-m", "chore: establish legacy fixture")
