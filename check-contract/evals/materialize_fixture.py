#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.resolve()
SKILLS_ROOT = ROOT.parents[1]
CANONICAL_MATERIALIZER = (
    SKILLS_ROOT / "exec-ticket" / "evals" / "materialize_fixture.py"
)
MANIFEST_PATH = ROOT / "fixture-manifest.json"
FIXTURES = ROOT / "fixtures"
CONTRACT = Path(".notes/feature-proj-123/contract")
VERSION = CONTRACT / "v1"
AUTHORITY_PATHS = (
    CONTRACT / "current.json",
    VERSION / "contract.md",
    VERSION / "approval.json",
    VERSION / "execution-ledger.md",
)
APPROVAL_ENV = {
    **os.environ,
    "GIT_AUTHOR_DATE": "2026-07-23T13:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-07-23T13:00:00+00:00",
}
IMPLEMENTATION_ENV = {
    **os.environ,
    "GIT_AUTHOR_DATE": "2026-07-23T13:05:00+00:00",
    "GIT_COMMITTER_DATE": "2026-07-23T13:05:00+00:00",
}
ASSERTION_CONTRACT_VERSION = 3
V3_OUTCOME = "Checkout can apply a validated percentage discount."
V2_OUTCOME = (
    "Checkout can apply a validated percentage discount without adding new "
    "structure."
)


def run(repo: Path, *args: str, env=None) -> str:
    return subprocess.run(
        args,
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def safe_relative(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"unsafe manifest path: {relative}")
    return path


def overlay_for(scenario: str, target: str) -> Path:
    base = FIXTURES / scenario
    if scenario == "contract-violated-summary":
        return base / f"{target}-overlay"
    return base / "overlay"


def copy_overlay(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def apply_future_v3_contract(cached: dict[Path, bytes]) -> None:
    contract_path = VERSION / "contract.md"
    contract = cached[contract_path].decode("utf-8")
    if contract.count(V2_OUTCOME) != 1:
        raise RuntimeError("canonical fixture does not contain the v2 Outcome")
    cached[contract_path] = contract.replace(V2_OUTCOME, V3_OUTCOME).encode()

    pricing_path = Path("src/pricing.py")
    pricing = cached[pricing_path].decode("utf-8")
    public_definition = "def validate_percentage(percentage):"
    if pricing.count(public_definition) != 1:
        raise RuntimeError("canonical fixture percentage validator is unexpected")
    cached[pricing_path] = pricing.replace(
        public_definition,
        "def _validate_percentage(percentage):",
    ).encode()

    approval_path = VERSION / "approval.json"
    approval = json.loads(cached[approval_path])
    approval["contract_sha256"] = hashlib.sha256(cached[contract_path]).hexdigest()
    cached[approval_path] = (
        json.dumps(approval, indent=2, sort_keys=True) + "\n"
    ).encode()


def inventory(repo: Path, base: str) -> list[dict[str, str]]:
    lines = run(repo, "git", "diff", "--name-status", f"{base}..HEAD").splitlines()
    return [
        {"status": status, "path": path}
        for status, path in (line.split("\t", 1) for line in lines if line)
    ]


def materialize_target(
    scenario: str,
    target_name: str,
    destination: Path,
    canonical: dict,
    expected: dict,
) -> dict:
    expected_head = expected["expected_head"]
    if not isinstance(expected_head, str) or len(expected_head) != 40:
        raise RuntimeError("manifest must pin an exact 40-character scenario HEAD")
    subprocess.run(
        [
            sys.executable,
            str(CANONICAL_MATERIALIZER),
            canonical["fixture"],
            str(destination),
        ],
        cwd=SKILLS_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    branch = run(destination, "git", "branch", "--show-current")
    head = run(destination, "git", "rev-parse", "HEAD")
    status = run(destination, "git", "status", "--porcelain")
    if branch != canonical["branch"] or head != canonical["head"] or status:
        raise RuntimeError("canonical fixture identity or cleanliness mismatch")

    approval = json.loads((destination / VERSION / "approval.json").read_text())
    contract = (destination / VERSION / "contract.md").read_bytes()
    if approval["base_sha"] != canonical["base"]:
        raise RuntimeError("canonical approval base mismatch")
    if hashlib.sha256(contract).hexdigest() != approval["contract_sha256"]:
        raise RuntimeError("canonical contract hash mismatch")
    if run(destination, "git", "merge-base", "--is-ancestor", canonical["base"], "HEAD"):
        raise RuntimeError("canonical approval base is not an ancestor")

    cached = {
        path: (destination / path).read_bytes()
        for path in AUTHORITY_PATHS
    }
    cached[Path("src/pricing.py")] = (destination / "src/pricing.py").read_bytes()
    apply_future_v3_contract(cached)

    run(destination, "git", "reset", "--hard", canonical["base"])
    run(destination, "git", "clean", "-fdx")
    if run(destination, "git", "rev-parse", "HEAD") != canonical["base"]:
        raise RuntimeError("disposable reset did not land on approval base")

    for relative, content in cached.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    run(destination, "git", "config", "user.name", "Check Contract Fixture")
    run(destination, "git", "config", "user.email", "check-fixture@example.invalid")
    run(destination, "git", "add", ".")
    run(
        destination,
        "git",
        "commit",
        "-q",
        "-m",
        "chore: publish approved PROJ-123 contract",
        env=APPROVAL_ENV,
    )

    copy_overlay(overlay_for(scenario, target_name), destination)
    ledger = destination / VERSION / "execution-ledger.md"
    if expected["ledger"] == "missing":
        ledger.unlink()
    elif expected["ledger"] == "empty":
        ledger.write_bytes(b"# Execution Ledger\n\n")

    run(destination, "git", "add", "-A")
    run(
        destination,
        "git",
        "commit",
        "-q",
        "-m",
        "chore: ship PROJ-123 implementation",
        env=IMPLEMENTATION_ENV,
    )

    actual_head = run(destination, "git", "rev-parse", "HEAD")
    actual_inventory = inventory(destination, canonical["base"])
    if actual_inventory != expected["inventory"]:
        raise RuntimeError(
            "changed-file inventory mismatch:\n"
            + json.dumps(actual_inventory, indent=2)
        )
    if actual_head != expected_head:
        raise RuntimeError(
            f"scenario HEAD mismatch: expected {expected_head}, "
            f"got {actual_head}"
        )
    if run(destination, "git", "status", "--porcelain=v1", "--ignored"):
        raise RuntimeError("scenario fixture contains dirty or ignored-generated paths")
    if run(
        destination,
        "git",
        "merge-base",
        "--is-ancestor",
        canonical["base"],
        "HEAD",
    ):
        raise RuntimeError("approval base is not an ancestor of scenario HEAD")

    declared = {item["path"] for item in expected["inventory"]}
    forbidden = {
        "fixture_setup.py",
        ".worker-results/validation.md",
        "tests/test_pricing.py",
    }
    tree = set(run(destination, "git", "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    if tree & forbidden or any(path.startswith(".fixture/") for path in tree):
        raise RuntimeError("canonical harness or narrative leaked into audited history")
    actual_changed = {item["path"] for item in actual_inventory}
    if actual_changed != declared:
        raise RuntimeError("manifest-declared changed path set mismatch")

    return {
        "base": canonical["base"],
        "branch": branch,
        "changed_file_inventory": actual_inventory,
        "contract_root": str((destination / CONTRACT).resolve()),
        "destination": str(destination.resolve()),
        "head": actual_head,
        "ledger_present": ledger.exists(),
    }


def materialize(scenario: str, destination: Path) -> dict:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if document.get("assertion_contract_version") != ASSERTION_CONTRACT_VERSION:
        raise RuntimeError("fixture manifest must declare assertion contract v3")
    if destination.exists():
        raise RuntimeError(f"destination already exists: {destination}")
    destination.mkdir(parents=True)
    scenario_manifest = document["scenarios"][scenario]
    targets = {}
    for target_name, expected in scenario_manifest["targets"].items():
        targets[target_name] = materialize_target(
            scenario,
            target_name,
            destination / target_name,
            document["canonical"],
            expected,
        )
    return {"scenario": scenario, "targets": targets}


def main() -> int:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=sorted(document["scenarios"]))
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        result = materialize(args.scenario, args.destination.resolve())
    except (
        json.JSONDecodeError,
        KeyError,
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
