#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class ContractStateError(RuntimeError):
    pass


_APPROVAL_TEXT_FIELDS = (
    "approved_at",
    "approved_by",
    "base_sha",
    "branch",
    "ticket",
)


def _json_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: dict) -> None:
    path.write_bytes(_json_bytes(value))


def _write_json_atomic(path: Path, value: dict) -> None:
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}-",
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        _write_json(temporary, value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, description: str) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ContractStateError(
            f"invalid UTF-8 in {description}: {path}"
        ) from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ContractStateError(
            f"invalid JSON in {description}: {path}"
        ) from error


def _active_version(root: Path) -> int:
    current = root / "current.json"
    if not current.exists():
        raise ContractStateError(f"missing current contract: {current}")
    value = _read_json(current, "current contract")
    if not isinstance(value, dict):
        raise ContractStateError(
            f"current contract must be a JSON object: {current}"
        )
    version = value.get("version")
    if type(version) is not int or version < 1:
        raise ContractStateError(f"invalid contract version in {current}")
    return version


def _validate_approval(approval: object, version: int) -> dict:
    if not isinstance(approval, dict):
        raise ContractStateError("approval must be a JSON object")

    for field in _APPROVAL_TEXT_FIELDS:
        value = approval.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ContractStateError(f"invalid approval field: {field}")

    digest = approval.get("contract_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ContractStateError("invalid approval field: contract_sha256")

    approval_version = approval.get("version")
    if type(approval_version) is not int or approval_version < 1:
        raise ContractStateError("invalid approval field: version")
    if approval_version != version:
        raise ContractStateError(
            f"approval version mismatch: expected {version}, "
            f"got {approval_version}"
        )
    return approval


def _verify_version_dir(
    version_dir: Path,
    version: int,
    allow_missing_ledger: bool = False,
) -> dict:
    contract_path = version_dir / "contract.md"
    approval_path = version_dir / "approval.json"
    ledger_path = version_dir / "execution-ledger.md"

    for path in (contract_path, approval_path):
        if not path.is_file():
            raise ContractStateError(f"missing contract artifact: {path}")
    ledger_present = ledger_path.is_file()
    if not ledger_present and (
        ledger_path.exists() or not allow_missing_ledger
    ):
        raise ContractStateError(f"missing contract artifact: {ledger_path}")

    approval = _validate_approval(
        _read_json(approval_path, "approval"),
        version,
    )
    expected = approval["contract_sha256"]
    actual = _sha256(contract_path)
    if expected != actual:
        raise ContractStateError(
            f"contract hash mismatch for v{version}: "
            f"expected {expected}, got {actual}"
        )

    return {
        "approval_path": str(approval_path),
        "contract_path": str(contract_path),
        "ledger_path": str(ledger_path),
        "ledger_present": ledger_present,
        "sha256": actual,
        "valid": True,
        "version": version,
    }


def _approval_value(
    *,
    approved_at: str,
    approved_by: str,
    base_sha: str,
    branch: str,
    contract_sha256: str,
    ticket: str,
    version: int,
) -> dict:
    return {
        "approved_at": approved_at,
        "approved_by": approved_by,
        "base_sha": base_sha,
        "branch": branch,
        "contract_sha256": contract_sha256,
        "ticket": ticket,
        "version": version,
    }


def approve(
    root: Path,
    draft: Path,
    ticket: str,
    branch: str,
    base_sha: str,
    approved_by: str,
    approved_at: str,
) -> dict:
    root = Path(root)
    draft = Path(draft)
    if not draft.is_file():
        raise ContractStateError(f"missing contract draft: {draft}")

    root.mkdir(parents=True, exist_ok=True)
    current = root / "current.json"
    draft_digest = _sha256(draft)
    if current.exists():
        active_version = _active_version(root)
        active_dir = root / f"v{active_version}"
        active_result = _verify_version_dir(active_dir, active_version)
        expected_active_approval = _approval_value(
            approved_at=approved_at,
            approved_by=approved_by,
            base_sha=base_sha,
            branch=branch,
            contract_sha256=draft_digest,
            ticket=ticket,
            version=active_version,
        )
        if (active_dir / "approval.json").read_bytes() == _json_bytes(
            expected_active_approval
        ):
            return active_result
        version = active_version + 1
    else:
        version = 1
    version_dir = root / f"v{version}"
    if version_dir.exists():
        expected_approval = _approval_value(
            approved_at=approved_at,
            approved_by=approved_by,
            base_sha=base_sha,
            branch=branch,
            contract_sha256=draft_digest,
            ticket=ticket,
            version=version,
        )
        result = _verify_version_dir(version_dir, version)
        stored_approval = _read_json(
            version_dir / "approval.json",
            "approval",
        )
        if stored_approval != expected_approval:
            raise ContractStateError(
                f"contract version already exists: {version_dir}"
            )
        _write_json_atomic(current, {"version": version})
        return result

    staging_dir = Path(
        tempfile.mkdtemp(
            dir=root,
            prefix=f".v{version}-",
        )
    )
    published = False
    activated = False
    try:
        contract_path = staging_dir / "contract.md"
        shutil.copyfile(draft, contract_path)
        digest = _sha256(contract_path)
        approval = _approval_value(
            approved_at=approved_at,
            approved_by=approved_by,
            base_sha=base_sha,
            branch=branch,
            contract_sha256=digest,
            ticket=ticket,
            version=version,
        )
        _write_json(staging_dir / "approval.json", approval)
        (staging_dir / "execution-ledger.md").write_text(
            "# Execution Ledger\n\n",
            encoding="utf-8",
        )
        _verify_version_dir(staging_dir, version)

        os.replace(staging_dir, version_dir)
        published = True
        result = _verify_version_dir(version_dir, version)
        _write_json_atomic(current, {"version": version})
        activated = True
        return result
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        if published and not activated:
            try:
                active_version = _active_version(root)
            except (ContractStateError, json.JSONDecodeError, OSError):
                active_version = None
            if active_version != version and version_dir.exists():
                shutil.rmtree(version_dir, ignore_errors=True)


def verify(
    root: Path,
    version: int | None = None,
    allow_missing_ledger: bool = False,
) -> dict:
    root = Path(root)
    resolved_version = version if version is not None else _active_version(root)
    if type(resolved_version) is not int or resolved_version < 1:
        raise ContractStateError(f"invalid contract version: {resolved_version}")
    version_dir = root / f"v{resolved_version}"
    return _verify_version_dir(
        version_dir,
        resolved_version,
        allow_missing_ledger,
    )


def _sanitize_branch(full_branch: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", full_branch)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value or value in {".", ".."}:
        raise ContractStateError(
            f"unsafe branch directory for branch: {full_branch!r}"
        )
    return value


def _has_published_state(root: Path) -> bool:
    if not root.is_dir():
        return False
    for path in root.iterdir():
        if re.fullmatch(r"\.v[1-9][0-9]*-.+", path.name):
            continue
        if re.fullmatch(r"\.current\.json-.+", path.name):
            continue
        return True
    return False


def _select_consumer_root(
    repository_root: Path,
    branch_directory: str,
) -> Path | None:
    roots = (
        repository_root / ".notes" / branch_directory / "contract",
        repository_root / "ai_docs" / branch_directory / "contract",
    )
    selected = [root for root in roots if (root / "current.json").exists()]
    if len(selected) == 2:
        raise ContractStateError(
            "ambiguous contract authority: current.json exists in both roots"
        )
    if selected:
        return selected[0]
    if any(_has_published_state(root) for root in roots):
        raise ContractStateError(
            "orphaned contract authority: published state has no current.json"
        )
    return None


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ContractStateError(
            f"git {' '.join(args)} failed: {detail}"
        )
    return result.stdout.strip()


def _canonical_repository_root(repo: Path) -> Path:
    return Path(_git(Path(repo), "rev-parse", "--show-toplevel")).resolve()


def _absent_consumer_result(
    repository_root: Path,
    branch_directory: str,
    branch: str,
    ticket: str,
    head_sha: str,
) -> dict:
    return {
        "active_version": None,
        "approval_path": None,
        "approval_sha256": None,
        "approval_version": None,
        "base_is_ancestor": None,
        "base_sha": None,
        "branch": branch,
        "branch_directory": branch_directory,
        "contract_path": None,
        "contract_sha256": None,
        "current_sha256": None,
        "head_sha": head_sha,
        "ledger_path": None,
        "ledger_present": False,
        "repository_root": str(repository_root),
        "selected_root": None,
        "state": "absent",
        "ticket": ticket,
    }


def resolve_consumer(
    repo: Path,
    branch: str,
    ticket: str,
    allow_missing_ledger: bool = False,
) -> dict:
    repository_root = _canonical_repository_root(Path(repo))
    branch_directory = _sanitize_branch(branch)
    selected_root = _select_consumer_root(
        repository_root,
        branch_directory,
    )
    head_sha = _git(repository_root, "rev-parse", "HEAD")
    if selected_root is None:
        return _absent_consumer_result(
            repository_root,
            branch_directory,
            branch,
            ticket,
            head_sha,
        )

    active_version = _active_version(selected_root)
    verified = verify(
        selected_root,
        active_version,
        allow_missing_ledger,
    )
    approval_path = Path(verified["approval_path"])
    approval = _read_json(approval_path, "approval")
    if approval["branch"] != branch:
        raise ContractStateError(
            f"approval branch mismatch: expected {branch}, "
            f"got {approval['branch']}"
        )
    if approval["ticket"] != ticket:
        raise ContractStateError(
            f"approval ticket mismatch: expected {ticket}, "
            f"got {approval['ticket']}"
        )

    base_sha = approval["base_sha"]
    if not re.fullmatch(r"[0-9a-f]{40,64}", base_sha):
        raise ContractStateError("approval base SHA must be a full commit SHA")
    resolved_base = _git(
        repository_root,
        "rev-parse",
        "--verify",
        f"{base_sha}^{{commit}}",
    )
    if resolved_base != base_sha:
        raise ContractStateError("approval base SHA must be a full commit SHA")
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "merge-base",
            "--is-ancestor",
            base_sha,
            head_sha,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode == 1:
        raise ContractStateError(
            f"approval base is not an ancestor of HEAD: {base_sha}"
        )
    if ancestry.returncode != 0:
        detail = ancestry.stderr.strip() or ancestry.stdout.strip()
        raise ContractStateError(f"git ancestry check failed: {detail}")

    approval_version = approval["version"]
    return {
        "active_version": active_version,
        "approval_path": verified["approval_path"],
        "approval_sha256": _sha256(approval_path),
        "approval_version": approval_version,
        "base_is_ancestor": True,
        "base_sha": base_sha,
        "branch": branch,
        "branch_directory": branch_directory,
        "contract_path": verified["contract_path"],
        "contract_sha256": verified["sha256"],
        "current_sha256": _sha256(selected_root / "current.json"),
        "head_sha": head_sha,
        "ledger_path": verified["ledger_path"],
        "ledger_present": verified["ledger_present"],
        "repository_root": str(repository_root),
        "selected_root": str(selected_root),
        "state": "approved",
        "ticket": ticket,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    approve_parser = commands.add_parser("approve")
    approve_parser.add_argument("--root", type=Path, required=True)
    approve_parser.add_argument("--draft", type=Path, required=True)
    approve_parser.add_argument("--ticket", required=True)
    approve_parser.add_argument("--branch", required=True)
    approve_parser.add_argument("--base-sha", required=True)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--approved-at", required=True)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--version", type=int)
    verify_parser.add_argument("--allow-missing-ledger", action="store_true")

    resolve_parser = commands.add_parser("resolve-consumer")
    resolve_parser.add_argument("--repo", type=Path, required=True)
    resolve_parser.add_argument("--branch", required=True)
    resolve_parser.add_argument("--ticket", required=True)
    resolve_parser.add_argument(
        "--allow-missing-ledger",
        action="store_true",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "approve":
            result = approve(
                root=args.root,
                draft=args.draft,
                ticket=args.ticket,
                branch=args.branch,
                base_sha=args.base_sha,
                approved_by=args.approved_by,
                approved_at=args.approved_at,
            )
        elif args.command == "verify":
            result = verify(
                args.root,
                args.version,
                args.allow_missing_ledger,
            )
        else:
            result = resolve_consumer(
                args.repo,
                args.branch,
                args.ticket,
                args.allow_missing_ledger,
            )
    except (ContractStateError, json.JSONDecodeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
