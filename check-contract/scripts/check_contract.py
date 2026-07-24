#!/usr/bin/env python3
"""Thin JSON CLI for the installed contract-audit runtime."""

import argparse
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path

from audit_runtime import (
    AuditComplete,
    AuditRuntime,
    AuditStopped,
    AuditTarget,
    ContinueAudit,
    NeedJudgment,
    StartAudit,
)


def parser():
    root = argparse.ArgumentParser(prog="check-contract")
    commands = root.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    start.add_argument("--repo", type=Path, required=True)
    start.add_argument("--branch", required=True)
    start.add_argument("--ticket", required=True)
    start.add_argument("--narrative", type=Path, action="append", default=[])
    start.add_argument("--then-repo", type=Path)
    start.add_argument("--then-branch")
    start.add_argument("--then-ticket")
    start.add_argument(
        "--then-narrative", type=Path, action="append", default=[]
    )
    start.add_argument("--deadline-seconds", type=int, default=300)

    continuation = commands.add_parser("continue")
    continuation.add_argument("--session", required=True)
    continuation.add_argument("--response", type=Path, required=True)
    return root


def command_from(args, argument_parser):
    if args.command == "continue":
        return ContinueAudit(
            session=args.session,
            response_path=args.response,
        )
    then_values = (args.then_repo, args.then_branch, args.then_ticket)
    if any(value is not None for value in then_values) and not all(
        value is not None for value in then_values
    ):
        argument_parser.error(
            "--then-repo, --then-branch, and --then-ticket "
            "must be supplied together"
        )
    if args.then_narrative and args.then_repo is None:
        argument_parser.error(
            "--then-narrative requires a complete then target"
        )
    primary = AuditTarget(
        repo=args.repo,
        branch=args.branch,
        ticket=args.ticket,
        narrative_paths=tuple(args.narrative),
    )
    then = None
    if args.then_repo is not None:
        then = AuditTarget(
            repo=args.then_repo,
            branch=args.then_branch,
            ticket=args.then_ticket,
            narrative_paths=tuple(args.then_narrative),
        )
    return StartAudit(
        primary=primary,
        then=then,
        deadline_seconds=args.deadline_seconds,
    )


def runtime_from_script_location():
    installed_root = Path(__file__).resolve().parents[2]
    rules = (
        installed_root
        / "change-contract"
        / "references"
        / "contract-check-rules.json"
    )
    if not rules.is_file():
        raise RuntimeError("installed contract-check rules are unavailable")
    return AuditRuntime()


def _public_value(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {
            key: _public_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_public_value(item) for item in value]
    if is_dataclass(value):
        return {
            field.name: _public_value(getattr(value, field.name))
            for field in fields(value)
        }
    raise TypeError("runtime returned a non-public value")


def as_public_dict(result):
    if not isinstance(
        result, (NeedJudgment, AuditComplete, AuditStopped)
    ):
        raise TypeError("runtime returned an unknown result")
    public = {"result": type(result).__name__, **_public_value(result)}
    if isinstance(result, AuditStopped):
        public["reason"] = "audit stopped"
    return public


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    result = runtime_from_script_location().advance(
        command_from(args, argument_parser)
    )
    print(
        json.dumps(
            as_public_dict(result),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if isinstance(result, (NeedJudgment, AuditComplete)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
