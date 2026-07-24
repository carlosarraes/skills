"""Guarded narrative disclosure and strict execution-ledger parsing."""

import hashlib
import importlib.util
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path


REPLAY_PROBE_PATH = (
    Path(__file__).resolve().parents[2]
    / "change-contract"
    / "scripts"
    / "replay_probe.py"
)
LEDGER_FIELDS = (
    ("affected_clauses", "Affected clauses"),
    ("discovered_fact", "Discovered fact"),
    ("actual_approach", "Actual approach"),
    ("reason_for_proceeding", "Reason for proceeding"),
    ("alternatives_considered", "Alternatives considered"),
    ("risk_delta", "Risk delta"),
    ("verification_evidence", "Verification evidence"),
)
HEADING_RE = re.compile(
    r"## (D[1-9][0-9]*) — "
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))"
    r" — (\S(?:.*\S)?)"
)
QA_HEADING_RE = re.compile(
    r"## QA evidence — \S+ (?:PASS|PASS WITH NOTES|FAIL) "
    r"<sub>\(@ ([0-9a-f]{7,40})\)</sub>"
)
NARRATIVE_BYTE_LIMIT = 2 * 1024 * 1024
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


class ReconciliationError(RuntimeError):
    """Raised when deferred narrative is stale or violates the closed grammar."""


@dataclass(frozen=True)
class ParsedLedgerEntry:
    ledger_id: str
    timestamp: str
    agent: str
    affected_clauses: str
    discovered_fact: str
    actual_approach: str
    reason_for_proceeding: str
    alternatives_considered: str
    risk_delta: str
    verification_evidence: str
    probe: object | None
    probe_descriptor: dict[str, object] | None

    def packet_value(self, evidence_id: str, probe_id: str | None) -> dict:
        value = {
            "ledger_id": self.ledger_id,
            "timestamp": self.timestamp,
            "agent": self.agent,
            **{
                name: getattr(self, name)
                for name, _ in LEDGER_FIELDS
            },
            "evidence_id": evidence_id,
            "probe_id": probe_id,
        }
        return value


@dataclass(frozen=True)
class GuardedNarrative:
    evidence_id: str
    source: str
    label: str
    content: object
    utf8_text: str | None

    def packet_value(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "label": self.label,
            "content": self.content,
        }


def _replay_module():
    spec = importlib.util.spec_from_file_location(
        "_contract_replay_probe",
        REPLAY_PROBE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _parse_probe(raw: str) -> tuple[object, dict[str, object]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReconciliationError("replay probe JSON is invalid") from error
    if (
        type(value) is not dict
        or json.dumps(
            value,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        != raw
    ):
        raise ReconciliationError(
            "replay probe must be canonical compact JSON"
        )
    try:
        probe = _replay_module().parse_replay_probe(value)
    except ValueError as error:
        raise ReconciliationError(str(error)) from error
    return probe, value


def parse_execution_ledger(content: bytes) -> tuple[ParsedLedgerEntry, ...]:
    """Parse only the exact, sequential D-entry markdown protocol."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReconciliationError("execution ledger must be UTF-8") from error
    lines = text.splitlines()
    if not lines or lines[0] != "# Execution Ledger":
        raise ReconciliationError(
            "execution ledger heading is missing or invalid"
        )
    if len(lines) > 1 and lines[1] != "":
        raise ReconciliationError(
            "execution ledger heading must be followed by a blank line"
        )
    index = 2
    entries = []
    while index < len(lines):
        while index < len(lines) and lines[index] == "":
            index += 1
        if index == len(lines):
            break
        match = HEADING_RE.fullmatch(lines[index])
        expected_id = f"D{len(entries) + 1}"
        if match is None or match.group(1) != expected_id:
            raise ReconciliationError(
                "execution ledger D IDs must be strict and sequential"
            )
        index += 1
        if index >= len(lines) or lines[index] != "":
            raise ReconciliationError(
                f"{expected_id} heading must be followed by a blank line"
            )
        index += 1
        fields = {}
        for name, label in LEDGER_FIELDS:
            prefix = f"- {label}: "
            if index >= len(lines) or not lines[index].startswith(prefix):
                raise ReconciliationError(
                    f"{expected_id} is missing ordered field {label}"
                )
            value = lines[index][len(prefix) :].strip()
            if not value:
                raise ReconciliationError(
                    f"{expected_id} field {label} must be non-empty"
                )
            fields[name] = value
            index += 1
        probe = None
        descriptor = None
        if (
            index < len(lines)
            and lines[index].startswith("- Replay probe: ")
        ):
            probe_line = lines[index]
            prefix = "- Replay probe: `"
            if not probe_line.startswith(prefix) or not probe_line.endswith("`"):
                raise ReconciliationError(
                    f"{expected_id} replay probe wrapper is invalid"
                )
            probe, descriptor = _parse_probe(probe_line[len(prefix) : -1])
            index += 1
        if index < len(lines) and lines[index] != "":
            raise ReconciliationError(
                f"{expected_id} contains an unknown or reordered field"
            )
        entries.append(
            ParsedLedgerEntry(
                ledger_id=expected_id,
                timestamp=match.group(2),
                agent=match.group(3),
                **fields,
                probe=probe,
                probe_descriptor=descriptor,
            )
        )
    return tuple(entries)


def _guard_keys(guard: object) -> dict[str, object]:
    if (
        type(guard) is not dict
        or set(guard) != {"path", "exists", "kind", "sha256"}
        or not isinstance(guard["path"], str)
        or not guard["path"]
        or not isinstance(guard["exists"], bool)
        or guard["kind"] not in {"absent", "file", "symlink", "other"}
        or (
            guard["sha256"] is not None
            and (
                not isinstance(guard["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", guard["sha256"]) is None
            )
        )
    ):
        raise ReconciliationError("narrative guard is invalid")
    return guard


def read_guarded_bytes(guard: object) -> bytes | None:
    """Read an exact guarded leaf without following its final symlink."""
    guard = _guard_keys(guard)
    path = Path(guard["path"])
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if guard != {
            "path": str(path),
            "exists": False,
            "kind": "absent",
            "sha256": None,
        }:
            raise ReconciliationError("guarded narrative changed after start")
        return None
    if not guard["exists"]:
        raise ReconciliationError("guarded narrative appeared after start")
    if stat.S_ISLNK(metadata.st_mode):
        kind = "symlink"
        content = os.fsencode(path.readlink())
    elif stat.S_ISREG(metadata.st_mode):
        kind = "file"
        try:
            descriptor = os.open(path, READ_FLAGS)
        except OSError as error:
            raise ReconciliationError(
                "guarded narrative is unavailable or unsafe"
            ) from error
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise ReconciliationError(
                    "guarded narrative changed type while reading"
                )
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > NARRATIVE_BYTE_LIMIT:
                    raise ReconciliationError(
                        "guarded narrative exceeds the byte limit"
                    )
                chunks.append(chunk)
            content = b"".join(chunks)
        finally:
            os.close(descriptor)
    else:
        kind = "other"
        content = (
            f"{stat.S_IFMT(metadata.st_mode)}:{metadata.st_size}"
        ).encode("ascii")
    if (
        guard["kind"] != kind
        or hashlib.sha256(content).hexdigest() != guard["sha256"]
    ):
        raise ReconciliationError("guarded narrative changed after start")
    if kind != "file":
        raise ReconciliationError(
            "guarded narrative must remain a regular file"
        )
    return content


def _encoded(content: bytes) -> tuple[object, str | None]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return {"encoding": "hex", "content": content.hex()}, None
    return text, text


def collect_guarded_narratives(
    state: dict[str, object],
) -> tuple[
    tuple[ParsedLedgerEntry, ...],
    tuple[GuardedNarrative, ...],
]:
    """Read every start-guarded narrative only after code validation."""
    ledger_content = read_guarded_bytes(state["ledger_guard"])
    entries = (
        ()
        if ledger_content is None
        else parse_execution_ledger(ledger_content)
    )
    narratives = []
    report_content = read_guarded_bytes(state["report_guard"])
    if report_content is not None:
        content, text = _encoded(report_content)
        narratives.append(
            GuardedNarrative(
                "report:PRIOR-1",
                "prior-report",
                "active prior check report",
                content,
                text,
            )
        )
    ledger_path = state["ledger_guard"]["path"]
    report_path = state["report_guard"]["path"]
    narrative_guards = state.get("narrative_guards")
    if type(narrative_guards) is not list:
        raise ReconciliationError("narrative guard list is invalid")
    seen = {ledger_path, report_path}
    narrative_index = 0
    for guard in narrative_guards:
        guard = _guard_keys(guard)
        if guard["path"] in seen:
            continue
        seen.add(guard["path"])
        content_bytes = read_guarded_bytes(guard)
        if content_bytes is None:
            continue
        narrative_index += 1
        content, text = _encoded(content_bytes)
        narratives.append(
            GuardedNarrative(
                f"narrative:N{narrative_index}",
                "supplied-or-deferred",
                Path(guard["path"]).name,
                content,
                text,
            )
        )
    return tuple(entries), tuple(narratives)


def acceptance_qa_exists(
    narratives: tuple[GuardedNarrative, ...],
    head_sha: str,
    base_sha: str,
) -> bool:
    for narrative in narratives:
        if (
            narrative.source != "supplied-or-deferred"
            or narrative.utf8_text is None
            or "<!-- qa-pr-evidence -->" not in narrative.utf8_text
        ):
            continue
        for line in narrative.utf8_text.splitlines():
            match = QA_HEADING_RE.fullmatch(line)
            if match is None:
                continue
            prefix = match.group(1)
            if (
                head_sha.startswith(prefix)
                and not base_sha.startswith(prefix)
            ):
                return True
    return False


def reconciliation_response_schema(
    nonce: str,
    ledger_ids: tuple[str, ...],
    deviation_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    probe_ids: tuple[str, ...],
) -> dict[str, object]:
    """Describe the one closed reconciliation response without circular IDs."""
    evidence_array = {
        "type": "array",
        "items": {"type": "string", "enum": list(evidence_ids)},
        "minItems": 1,
        "uniqueItems": True,
    }
    ledger_item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ledger_id",
            "status",
            "evidence_ids",
            "reason",
        ],
        "properties": {
            "ledger_id": {
                "type": "string",
                "enum": list(ledger_ids),
            },
            "status": {
                "type": "string",
                "enum": [
                    "VERIFIED",
                    "QUESTIONABLE",
                    "CONTRADICTED",
                ],
            },
            "evidence_ids": evidence_array,
            "reason": {"type": "string", "minLength": 1},
        },
    }
    match_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["deviation_id", "ledger_id"],
        "properties": {
            "deviation_id": {
                "type": "string",
                "enum": list(deviation_ids),
            },
            "ledger_id": {
                "type": "string",
                "enum": list(ledger_ids),
            },
        },
    }
    probe_schema = (
        {
            "oneOf": [
                {"type": "null"},
                {"type": "string", "enum": list(probe_ids)},
            ]
        }
        if probe_ids
        else {"type": "null"}
    )
    judgment = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ledger_entries",
            "deviation_matches",
            "contract_obsolete",
            "selected_probe_id",
        ],
        "properties": {
            "ledger_entries": {
                "type": "array",
                "items": ledger_item,
                "minItems": len(ledger_ids),
                "maxItems": len(ledger_ids),
            },
            "deviation_matches": {
                "type": "array",
                "items": match_item,
            },
            "contract_obsolete": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "evidence_ids", "reason"],
                "properties": {
                    "value": {"type": "boolean"},
                    "evidence_ids": evidence_array,
                    "reason": {"type": "string", "minLength": 1},
                },
            },
            "selected_probe_id": probe_schema,
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "session",
            "nonce",
            "packet_sha256",
            "kind",
            "judgment",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "session": {
                "type": "string",
                "pattern": "^[0-9a-f]{32}\\.[0-9a-f]{64}$",
            },
            "nonce": {"const": nonce},
            "packet_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "kind": {"const": "reconciliation"},
            "judgment": judgment,
        },
    }
