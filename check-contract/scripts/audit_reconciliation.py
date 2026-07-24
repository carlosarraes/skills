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


IDENTITY_GUARD_KEYS = {
    "path",
    "exists",
    "kind",
    "dev",
    "ino",
    "mode",
    "size",
    "mtime_ns",
    "ctime_ns",
}


def _guard_keys(guard: object) -> dict[str, object]:
    if (
        type(guard) is not dict
        or set(guard) != IDENTITY_GUARD_KEYS
        or not isinstance(guard["path"], str)
        or not guard["path"]
        or not isinstance(guard["exists"], bool)
        or guard["kind"] not in {"absent", "file", "symlink", "other"}
    ):
        raise ReconciliationError("narrative guard is invalid")
    values = (
        guard["dev"],
        guard["ino"],
        guard["mode"],
        guard["size"],
        guard["mtime_ns"],
        guard["ctime_ns"],
    )
    if guard["exists"]:
        if any(type(value) is not int or value < 0 for value in values):
            raise ReconciliationError("narrative identity guard is invalid")
    elif (
        guard["kind"] != "absent"
        or any(value is not None for value in values)
    ):
        raise ReconciliationError("absent narrative guard is invalid")
    return guard


def _identity_value(path: Path, metadata) -> dict[str, object]:
    if stat.S_ISREG(metadata.st_mode):
        kind = "file"
    elif stat.S_ISLNK(metadata.st_mode):
        kind = "symlink"
    else:
        kind = "other"
    return {
        "path": str(path),
        "exists": True,
        "kind": kind,
        "dev": metadata.st_dev,
        "ino": metadata.st_ino,
        "mode": metadata.st_mode,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
    }


def read_guarded_bytes(
    guard: object,
) -> tuple[bytes | None, dict[str, object]]:
    """Read an exact guarded leaf without following its final symlink."""
    guard = _guard_keys(guard)
    path = Path(guard["path"])
    if not guard["exists"]:
        try:
            path.lstat()
        except FileNotFoundError:
            return None, {**guard, "sha256": None}
        raise ReconciliationError("guarded narrative appeared after start")
    if guard["kind"] == "file":
        try:
            descriptor = os.open(path, READ_FLAGS | os.O_NONBLOCK)
        except OSError as error:
            raise ReconciliationError(
                "guarded narrative is unavailable or unsafe"
            ) from error
        try:
            opened = os.fstat(descriptor)
            if _identity_value(path, opened) != guard:
                raise ReconciliationError(
                    "guarded narrative identity changed after start"
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
        try:
            actual = _identity_value(path, path.lstat())
        except FileNotFoundError as error:
            raise ReconciliationError(
                "guarded narrative disappeared after start"
            ) from error
        if actual != guard:
            raise ReconciliationError(
                "guarded narrative identity changed after start"
            )
        raise ReconciliationError(
            "guarded narrative must remain a regular file"
        )
    return content, {
        **guard,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


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
    dict[str, object],
]:
    """Read every start-guarded narrative only after code validation."""
    ledger_content, ledger_content_guard = read_guarded_bytes(
        state["ledger_guard"]
    )
    entries = (
        ()
        if ledger_content is None
        else parse_execution_ledger(ledger_content)
    )
    narratives = []
    report_content, report_content_guard = read_guarded_bytes(
        state["report_guard"]
    )
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
    narrative_content_guards = []
    for guard in narrative_guards:
        guard = _guard_keys(guard)
        if guard["path"] in seen:
            continue
        seen.add(guard["path"])
        content_bytes, content_guard = read_guarded_bytes(guard)
        narrative_content_guards.append(content_guard)
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
    return (
        tuple(entries),
        tuple(narratives),
        {
            "ledger": ledger_content_guard,
            "report": report_content_guard,
            "narratives": narrative_content_guards,
        },
    )


def qa_head_references(
    narratives: tuple[GuardedNarrative, ...],
) -> tuple[str, ...]:
    references = []
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
            references.append(match.group(1))
    return tuple(sorted(set(references)))


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
    optional_evidence_array = {
        **evidence_array,
        "minItems": 0,
    }
    ledger_item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "evidence_ids",
            "reason",
        ],
        "properties": {
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
            "probe_id",
        ],
        "properties": {
            "ledger_entries": {
                "type": "object",
                "additionalProperties": False,
                "required": list(ledger_ids),
                "properties": {
                    ledger_id: ledger_item
                    for ledger_id in ledger_ids
                },
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
                    "evidence_ids": optional_evidence_array,
                    "reason": {"type": "string", "minLength": 1},
                },
            },
            "probe_id": probe_schema,
        },
        "allOf": [
            {
                "if": {
                    "properties": {
                        "contract_obsolete": {
                            "type": "object",
                            "required": ["value"],
                            "properties": {
                                "value": {"const": True},
                            },
                        }
                    }
                },
                "then": {
                    "properties": {
                        "contract_obsolete": {
                            "properties": {
                                "evidence_ids": evidence_array,
                            }
                        }
                    }
                },
            }
        ],
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
