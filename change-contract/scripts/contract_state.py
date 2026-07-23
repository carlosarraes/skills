#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


class ContractStateError(RuntimeError):
    pass


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _active_version(root: Path) -> int:
    current = root / "current.json"
    if not current.exists():
        raise ContractStateError(f"missing current contract: {current}")
    value = json.loads(current.read_text(encoding="utf-8"))
    version = value.get("version")
    if not isinstance(version, int) or version < 1:
        raise ContractStateError(f"invalid contract version in {current}")
    return version


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
    version = _active_version(root) + 1 if current.exists() else 1
    version_dir = root / f"v{version}"
    if version_dir.exists():
        raise ContractStateError(f"contract version already exists: {version_dir}")

    version_dir.mkdir()
    contract_path = version_dir / "contract.md"
    shutil.copyfile(draft, contract_path)
    digest = _sha256(contract_path)
    approval = {
        "approved_at": approved_at,
        "approved_by": approved_by,
        "base_sha": base_sha,
        "branch": branch,
        "contract_sha256": digest,
        "ticket": ticket,
        "version": version,
    }
    _write_json(version_dir / "approval.json", approval)
    (version_dir / "execution-ledger.md").write_text(
        "# Execution Ledger\n\n",
        encoding="utf-8",
    )
    _write_json(current, {"version": version})
    return verify(root, version)


def verify(root: Path, version: int | None = None) -> dict:
    root = Path(root)
    resolved_version = version if version is not None else _active_version(root)
    version_dir = root / f"v{resolved_version}"
    contract_path = version_dir / "contract.md"
    approval_path = version_dir / "approval.json"
    ledger_path = version_dir / "execution-ledger.md"

    for path in (contract_path, approval_path, ledger_path):
        if not path.is_file():
            raise ContractStateError(f"missing contract artifact: {path}")

    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    expected = approval.get("contract_sha256")
    actual = _sha256(contract_path)
    if expected != actual:
        raise ContractStateError(
            f"contract hash mismatch for v{resolved_version}: "
            f"expected {expected}, got {actual}"
        )

    return {
        "approval_path": str(approval_path),
        "contract_path": str(contract_path),
        "ledger_path": str(ledger_path),
        "sha256": actual,
        "valid": True,
        "version": resolved_version,
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
