#!/usr/bin/env python3
"""Thin JSON CLI for the installed contract-audit runtime."""

import argparse
import base64
import hashlib
import json
import os
import sys
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
from audit_broker import BrokerError, broker_call


def parser():
    root = argparse.ArgumentParser(prog="check-contract")
    commands = root.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    start.add_argument("--repo", type=Path)
    start.add_argument("--branch")
    start.add_argument("--ticket")
    start.add_argument("--request-id")
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
    primary_values = (args.repo, args.branch, args.ticket)
    if any(value is not None for value in primary_values) and not all(
        value is not None for value in primary_values
    ):
        argument_parser.error(
            "--repo, --branch, and --ticket must be supplied together"
        )
    if args.request_id is None and args.repo is None:
        argument_parser.error(
            "manual start requires --repo, --branch, and --ticket"
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
    if args.narrative and args.repo is None:
        argument_parser.error("--narrative requires a complete primary target")
    primary = (
        AuditTarget(
            repo=args.repo,
            branch=args.branch,
            ticket=args.ticket,
            narrative_paths=tuple(args.narrative),
        )
        if args.repo is not None
        else None
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
        request_id=args.request_id,
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
    for optional in ("request_id", "deadline_stage"):
        if public.get(optional) is None:
            public.pop(optional, None)
    if isinstance(result, AuditStopped):
        public["reason"] = "audit stopped"
    return public


def _broker_command(args, argument_parser, socket_path):
    if args.command == "start":
        supplied_targets = (
            args.repo,
            args.branch,
            args.ticket,
            args.then_repo,
            args.then_branch,
            args.then_ticket,
            *args.narrative,
            *args.then_narrative,
        )
        if args.request_id is None or any(
            value is not None for value in supplied_targets
        ):
            argument_parser.error(
                "broker start accepts only --request-id"
            )
        return broker_call(
            socket_path,
            {"operation": "start", "request_id": args.request_id},
        )
    try:
        response = args.response.read_bytes()
    except OSError as error:
        argument_parser.error(f"cannot read broker response: {error}")
    return broker_call(
        socket_path,
        {
            "operation": "continue",
            "session": args.session,
            "response_base64": base64.b64encode(response).decode("ascii"),
        },
    )


def _materialize_broker_result(result):
    if result.get("result") != "NeedJudgment":
        return result
    packet = result.pop("packet", None)
    if type(packet) is not dict:
        raise RuntimeError("broker omitted the issued packet")
    packet_bytes = (
        json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if hashlib.sha256(packet_bytes).hexdigest() != result["packet_sha256"]:
        raise RuntimeError("broker packet hash mismatch")
    packet_request = packet.get("request")
    if (
        type(packet_request) is not dict
        or packet_request.get("id") != result.get("request_id")
    ):
        raise RuntimeError("broker packet request binding mismatch")
    client_root_value = os.environ.get("CHECK_CONTRACT_CLIENT_ROOT")
    if not client_root_value:
        raise RuntimeError("broker client root is not configured")
    client_root = Path(client_root_value)
    client_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    packet_path = client_root / f"packet-{result['packet_sha256']}.json"
    if packet_path.exists():
        if packet_path.read_bytes() != packet_bytes:
            raise RuntimeError("broker packet destination changed")
    else:
        packet_path.write_bytes(packet_bytes)
    response_path = client_root / f"response-{result['nonce']}.json"
    result.update(
        {
            "packet_path": str(packet_path),
            "response_path": str(response_path),
            "next_command": [
                sys.executable,
                str(Path(__file__).resolve()),
                "continue",
                "--session",
                result["session"],
                "--response",
                str(response_path),
            ],
        }
    )
    return result


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    broker_socket = os.environ.get("CHECK_CONTRACT_BROKER_SOCKET")
    installed_root = Path(__file__).resolve().parents[2]
    broker_required = (
        installed_root == Path("/tmp/check-contract-runtime")
        and Path("/tmp/check-contract-broker-required").exists()
    )
    if broker_required and not broker_socket:
        argument_parser.error("this runtime requires its host audit broker")
    if broker_socket:
        try:
            public = _materialize_broker_result(
                _broker_command(args, argument_parser, broker_socket)
            )
        except BrokerError as error:
            public = {
                "result": "AuditStopped",
                "code": error.code,
                "reason": "audit stopped",
                "target": "broker",
                "prior_report_preserved": True,
                "zero_target_writes": True,
            }
        successful = public.get("result") in {
            "NeedJudgment",
            "AuditComplete",
        }
    else:
        result = runtime_from_script_location().advance(
            command_from(args, argument_parser)
        )
        public = as_public_dict(result)
        successful = isinstance(result, (NeedJudgment, AuditComplete))
    print(
        json.dumps(
            public,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if successful else 2


if __name__ == "__main__":
    raise SystemExit(main())
