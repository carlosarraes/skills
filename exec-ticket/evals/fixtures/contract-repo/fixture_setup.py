#!/usr/bin/env python3
import hashlib
import json
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

post_pricing = (ROOT / "src" / "pricing.py").read_bytes()
(ROOT / "src" / "pricing.py").write_bytes(
    (ROOT / ".fixture" / "base-pricing.py").read_bytes()
)

git("init", "-q")
git("config", "user.name", "Fixture")
git("config", "user.email", "fixture@example.invalid")
git("checkout", "-q", "-b", "feature/proj-123")
git("add", "plan.md", "src", "tests/test_checkout.py")
git("commit", "-q", "-m", "chore: establish contract base")
base_sha = git("rev-parse", "HEAD")

(ROOT / "src" / "pricing.py").write_bytes(post_pricing)
contract = (
    ROOT
    / ".notes"
    / "feature-proj-123"
    / "contract"
    / "v1"
    / "contract.md"
)
contract.write_text(
    contract.read_text(encoding="utf-8").replace(
        "Base commit: SET_BY_FIXTURE_SETUP",
        f"Base commit: {base_sha}",
    ),
    encoding="utf-8",
)
approval = contract.with_name("approval.json")
value = json.loads(approval.read_text(encoding="utf-8"))
value["base_sha"] = base_sha
value["contract_sha256"] = hashlib.sha256(contract.read_bytes()).hexdigest()
approval.write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

git("add", ".")
git("commit", "-q", "-m", "chore: add approved contract and shared validator")
