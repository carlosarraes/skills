#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
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


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _verify_version_dir(version_dir: Path, version: int) -> dict:
    contract_path = version_dir / "contract.md"
    approval_path = version_dir / "approval.json"
    ledger_path = version_dir / "execution-ledger.md"

    for path in (contract_path, approval_path, ledger_path):
        if not path.is_file():
            raise ContractStateError(f"missing contract artifact: {path}")

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
    if current.exists():
        active_version = _active_version(root)
        _verify_version_dir(root / f"v{active_version}", active_version)
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
            contract_sha256=_sha256(draft),
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


def verify(root: Path, version: int | None = None) -> dict:
    root = Path(root)
    resolved_version = version if version is not None else _active_version(root)
    if type(resolved_version) is not int or resolved_version < 1:
        raise ContractStateError(f"invalid contract version: {resolved_version}")
    version_dir = root / f"v{resolved_version}"
    return _verify_version_dir(version_dir, resolved_version)


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
        else:
            result = verify(args.root, args.version)
    except (ContractStateError, json.JSONDecodeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
