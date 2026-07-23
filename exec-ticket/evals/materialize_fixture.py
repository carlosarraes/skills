#!/usr/bin/env python3
import argparse
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.resolve()
MANIFEST = ROOT / "fixture-manifest.json"
FIXTURES = ROOT / "fixtures"


def command(repo: Path, *args: str) -> str:
    return subprocess.run(
        args,
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def materialize(name: str, destination: Path) -> dict:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fixture = document["fixtures"][name]
    template = FIXTURES / name
    if destination.exists():
        raise RuntimeError(f"destination already exists: {destination}")
    shutil.copytree(template, destination)

    for relative, encoded in fixture["binary_overrides"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"unsafe fixture override: {relative}")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(encoded, validate=True))

    subprocess.run(
        [sys.executable, "fixture_setup.py"],
        cwd=destination,
        check=True,
        capture_output=True,
        text=True,
    )
    branch = command(destination, "git", "branch", "--show-current")
    head = command(destination, "git", "rev-parse", "HEAD")
    status = command(destination, "git", "status", "--porcelain")
    if branch != fixture["expected_branch"]:
        raise RuntimeError(
            f"fixture branch mismatch: expected {fixture['expected_branch']}, "
            f"got {branch}"
        )
    if head != fixture["expected_head"]:
        raise RuntimeError(
            f"fixture HEAD mismatch: expected {fixture['expected_head']}, "
            f"got {head}"
        )
    if status:
        raise RuntimeError(f"materialized fixture is dirty:\n{status}")
    return {
        "branch": branch,
        "destination": str(destination.resolve()),
        "head": head,
        "name": name,
    }


def main() -> int:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", choices=sorted(document["fixtures"]))
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        result = materialize(args.fixture, args.destination.resolve())
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
