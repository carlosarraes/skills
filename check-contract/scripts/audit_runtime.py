"""Deep public facade for contract-audit policy and runtime orchestration."""

import hashlib
import json
import math
import os
import re
import secrets
import stat
import tempfile
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

from audit_evidence import (
    AuthorityError,
    ContractParseError,
    EvidenceError,
    LocalGitRunner,
    capture_code_evidence,
    parse_contract,
    resolve_authority,
)
from audit_domain import (
    AuditDecision,
    AuditInputError,
    AxisItem,
    ClauseJudgment,
    CodeJudgment,
    Deviation,
    DeviationMatch,
    Finding,
    LedgerEntry,
    PathAssessment,
    ReconciliationJudgment,
    RulePack,
    SurfaceJudgment,
    load_rules,
)
from audit_policy import aggregate
from audit_session import (
    ClaimedResponseError,
    SessionIntegrityError,
    SessionStore,
)
from audit_validation import validate_code_judgment
from audit_reconciliation import (
    ReconciliationError,
    acceptance_qa_exists,
    collect_guarded_narratives,
    reconciliation_response_schema,
)


def _deep_freeze(value):
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise TypeError("public envelope floats must be finite")
        return value
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("public envelope mapping keys must be strings")
            frozen[key] = _deep_freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    raise TypeError(
        "public envelope contains an unsupported mutable or domain value"
    )


def _guard_path(path: Path) -> dict[str, object]:
    path = Path(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {
            "path": str(path),
            "exists": False,
            "kind": "absent",
            "sha256": None,
        }
    if stat.S_ISREG(metadata.st_mode):
        content = path.read_bytes()
        kind = "file"
    elif stat.S_ISLNK(metadata.st_mode):
        content = os.fsencode(path.readlink())
        kind = "symlink"
    else:
        content = (
            f"{stat.S_IFMT(metadata.st_mode)}:{metadata.st_size}"
        ).encode("ascii")
        kind = "other"
    return {
        "path": str(path),
        "exists": True,
        "kind": kind,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


@dataclass(frozen=True)
class AuditTarget:
    repo: Path
    branch: str
    ticket: str
    narrative_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class StartAudit:
    primary: AuditTarget
    then: AuditTarget | None = None
    deadline_seconds: int = 300


@dataclass(frozen=True)
class ContinueAudit:
    session: str
    response_path: Path


@dataclass(frozen=True)
class NeedJudgment:
    session: str
    target: str
    kind: str
    packet_path: Path
    packet_sha256: str
    response_path: Path
    next_command: tuple[str, ...]
    nonce: str
    a_closure_digest: str | None = None
    closed_target: Mapping[str, object] | None = None

    def __post_init__(self):
        if self.closed_target is not None:
            if not isinstance(self.closed_target, Mapping):
                raise TypeError("closed_target must be a mapping or None")
            object.__setattr__(
                self,
                "closed_target",
                _deep_freeze(self.closed_target),
            )


@dataclass(frozen=True)
class AuditComplete:
    verdict: str
    route: tuple[str, ...]
    report_path: Path
    report_sha256: str
    mutation_attestation: Mapping[str, object]

    def __post_init__(self):
        if not isinstance(self.mutation_attestation, Mapping):
            raise TypeError("mutation_attestation must be a mapping")
        object.__setattr__(
            self,
            "mutation_attestation",
            _deep_freeze(self.mutation_attestation),
        )


@dataclass(frozen=True)
class AuditStopped:
    code: str
    reason: str
    target: str
    prior_report_preserved: bool
    zero_target_writes: bool


class AuditRuntime:
    """Advance one closed audit transition while keeping evidence internals deep."""

    def __init__(
        self,
        *,
        session_root: Path | None = None,
        clock=time.monotonic,
        authority_resolver=resolve_authority,
        git_runner=None,
        nonce_factory=None,
    ):
        default_root = Path(tempfile.gettempdir()) / "contract-audit-sessions"
        self.session_root = Path(
            os.path.abspath(session_root or default_root)
        )
        self.clock = clock
        self.authority_resolver = authority_resolver
        self.git_runner = git_runner or LocalGitRunner(clock)
        self.nonce_factory = nonce_factory or (lambda: secrets.token_hex(16))

    def _stopped(self, code, reason, target="primary"):
        return AuditStopped(
            code=code,
            reason=str(reason),
            target=target,
            prior_report_preserved=True,
            zero_target_writes=True,
        )

    def advance(self, transition):
        if isinstance(transition, ContinueAudit):
            return self._continue(transition)
        if not isinstance(transition, StartAudit):
            return self._stopped(
                "TRANSITION_INVALID",
                "transition must be StartAudit or ContinueAudit",
            )
        if transition.then is not None:
            return self._stopped(
                "COMPOUND_UNAVAILABLE",
                "compound audit transitions are deferred",
            )
        return self._start(transition)

    def _nonce(self):
        value = self.nonce_factory()
        if not isinstance(value, str) or re.fullmatch(
            r"[0-9a-f]{32}", value
        ) is None:
            raise SessionIntegrityError(
                "nonce factory returned an invalid nonce"
            )
        return value

    def _terminal_state(self, state, code):
        value = dict(state)
        value.update(
            {
                "phase": "terminal",
                "nonce": self._nonce(),
                "response_name": f"{self._nonce()}.json",
                "terminal_code": code,
            }
        )
        return value

    def _stop_after_claim(self, store, token, state, code, reason):
        try:
            store.tombstone_claimed(
                token,
                self._terminal_state(state, code),
            )
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped(
                "SESSION_FAILURE",
                f"{reason}; terminal state failed: {error}",
                state.get("target", "session"),
            )
        return self._stopped(
            code,
            reason,
            state.get("target", "session"),
        )

    def _response_envelope(self, raw, token, state):
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AuditInputError(
                "response must be one UTF-8 JSON object"
            ) from error
        expected = {
            "schema_version",
            "session",
            "nonce",
            "packet_sha256",
            "kind",
            "judgment",
        }
        if type(value) is not dict or set(value) != expected:
            raise AuditInputError(
                "response envelope has extra or missing JSON keys"
            )
        if type(value["schema_version"]) is not int or value[
            "schema_version"
        ] != 1:
            raise AuditInputError(
                "response schema_version must be exactly 1"
            )
        checks = (
            ("session", token),
            ("nonce", state["nonce"]),
            ("packet_sha256", state["packet_sha256"]),
            ("kind", state["phase"]),
        )
        for field, expected_value in checks:
            actual = value[field]
            if not isinstance(actual, str) or not secrets.compare_digest(
                actual,
                expected_value,
            ):
                raise AuditInputError(
                    f"response {field} does not match the issued generation"
                )
        if type(value["judgment"]) is not dict:
            raise AuditInputError("response judgment must be a JSON object")
        return value["judgment"]

    def _code_value(self, judgment):
        return asdict(judgment)

    def _issue_reconciliation(
        self,
        store,
        token,
        state,
        code_packet,
        code_judgment,
    ):
        entries, narratives = collect_guarded_narratives(state)
        issued_probes = {}
        ledger_values = []
        evidence = {}
        for clause in code_packet["clauses"]:
            evidence[f"contract:{clause['clause_id']}"] = clause
        code_value = self._code_value(code_judgment)
        for clause in code_value["clauses"]:
            evidence[f"code:{clause['clause_id']}"] = clause
        for path in code_value["path_assessments"]:
            evidence[f"code-path:{path['path_id']}"] = path
        for deviation in code_value["deviations"]:
            evidence[
                f"code-deviation:{deviation['deviation_id']}"
            ] = deviation
        for entry in entries:
            evidence_id = f"ledger:{entry.ledger_id}"
            probe_id = None
            if entry.probe_descriptor is not None:
                probe_id = f"Q{len(issued_probes) + 1}"
                issued_probes[probe_id] = entry.probe_descriptor
            ledger_value = entry.packet_value(evidence_id, probe_id)
            ledger_values.append(ledger_value)
            evidence[evidence_id] = {
                key: value
                for key, value in ledger_value.items()
                if key not in {"evidence_id", "probe_id"}
            }
        for narrative in narratives:
            evidence[narrative.evidence_id] = narrative.packet_value()
        qa_exists = acceptance_qa_exists(
            narratives,
            state["recorded_range"]["head_sha"],
            state["recorded_range"]["base_sha"],
        )
        evidence["runtime:QA-1"] = {
            "acceptance_qa_exists": qa_exists,
            "rule": (
                "guarded supplied/deferred qa-pr marker "
                "and recorded-HEAD heading"
            ),
        }
        reuse_indeterminate = bool(
            code_packet["reuse_coverage_indeterminate"]
        )
        evidence["runtime:REUSE-COVERAGE-1"] = {
            "reuse_coverage_indeterminate": reuse_indeterminate,
            "source": "recorded full-HEAD search capture",
        }
        evidence_ids = tuple(evidence)
        deviations = code_value["deviations"]
        deviation_ids = tuple(
            item["deviation_id"] for item in deviations
        )
        ledger_ids = tuple(item.ledger_id for item in entries)
        probe_ids = tuple(issued_probes)
        nonce = self._nonce()
        next_state = {
            **state,
            "phase": "reconciliation",
            "nonce": nonce,
            "response_name": f"{self._nonce()}.json",
            "code_judgment": code_value,
            "ledger_entries": ledger_values,
            "issued_probes": issued_probes,
            "acceptance_qa_exists": qa_exists,
            "reuse_coverage_indeterminate": reuse_indeterminate,
            "reconciliation_evidence_ids": list(evidence_ids),
        }
        packet = {
            "schema_version": 1,
            "kind": "reconciliation",
            "authority": code_packet["authority"],
            "recorded_range": {
                "base_sha": code_packet["authority"]["base_sha"],
                "head_sha": code_packet["authority"]["head_sha"],
            },
            "clauses": code_packet["clauses"],
            "clause_ids": code_packet["clause_ids"],
            "code_judgment": code_value,
            "ledger_entries": ledger_values,
            "deviations": deviations,
            "deviation_ids": list(deviation_ids),
            "probe_ids": list(probe_ids),
            "narratives": [
                item.packet_value() for item in narratives
            ],
            "evidence": evidence,
            "evidence_ids": list(evidence_ids),
            "acceptance_qa_exists": qa_exists,
            "runtime_facts": {
                "reuse_coverage_indeterminate": reuse_indeterminate,
                "reuse_evidence_id": "runtime:REUSE-COVERAGE-1",
                "acceptance_qa_evidence_id": "runtime:QA-1",
            },
            "response_schema": reconciliation_response_schema(
                nonce,
                ledger_ids,
                deviation_ids,
                evidence_ids,
                probe_ids,
            ),
        }
        generation = store.append_claimed(token, next_state, packet)
        return NeedJudgment(
            session=generation.token,
            target=state["target"],
            kind="reconciliation",
            packet_path=generation.packet_path,
            packet_sha256=generation.packet_sha256,
            response_path=generation.response_path,
            next_command=(
                "check-contract-runtime",
                "continue",
                "--session",
                generation.token,
                "--response",
                str(generation.response_path),
            ),
            nonce=nonce,
        )

    def _continue(self, request):
        store = SessionStore(self.session_root)
        try:
            state = store.load(request.session)
            packet = store.load_packet(request.session)
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped("SESSION_INVALID", error, "session")
        if state["phase"] != "code":
            try:
                store.claim(request.session)
            except (SessionIntegrityError, OSError, ValueError) as error:
                return self._stopped(
                    "SESSION_INVALID",
                    error,
                    state.get("target", "session"),
                )
            return self._stop_after_claim(
                store,
                request.session,
                state,
                "OUT_OF_PHASE",
                "generation is not in the code-judgment phase",
            )
        try:
            raw = store.claim_and_read(
                request.session,
                request.response_path,
            )
        except ClaimedResponseError as error:
            return self._stop_after_claim(
                store,
                request.session,
                state,
                "RESPONSE_INVALID",
                error,
            )
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped(
                "SESSION_INVALID",
                error,
                state.get("target", "session"),
            )
        if self.clock() > state["absolute_deadline"]:
            return self._stop_after_claim(
                store,
                request.session,
                state,
                "DEADLINE_EXPIRED",
                "audit deadline expired before response validation",
            )
        try:
            judgment_value = self._response_envelope(
                raw,
                request.session,
                state,
            )
            code_judgment = validate_code_judgment(
                packet,
                judgment_value,
            )
        except (AuditInputError, KeyError, TypeError, ValueError) as error:
            return self._stop_after_claim(
                store,
                request.session,
                state,
                "RESPONSE_INVALID",
                error,
            )
        try:
            return self._issue_reconciliation(
                store,
                request.session,
                state,
                packet,
                code_judgment,
            )
        except ReconciliationError as error:
            return self._stop_after_claim(
                store,
                request.session,
                state,
                "NARRATIVE_INVALID",
                error,
            )
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stop_after_claim(
                store,
                request.session,
                state,
                "SESSION_FAILURE",
                error,
            )

    def _start(self, request: StartAudit):
        target = request.primary
        if not isinstance(target, AuditTarget):
            return self._stopped(
                "TARGET_INVALID",
                "primary must be an AuditTarget",
            )
        if (
            type(request.deadline_seconds) is not int
            or request.deadline_seconds <= 0
        ):
            return self._stopped(
                "DEADLINE_INVALID",
                "deadline_seconds must be a positive integer",
            )
        started_at = self.clock()
        absolute_deadline = started_at + min(request.deadline_seconds, 300)
        try:
            authority = self.authority_resolver(
                Path(target.repo),
                target.branch,
                target.ticket,
            )
        except (AuthorityError, OSError, ValueError) as error:
            return self._stopped("AUTHORITY_INVALID", error)
        try:
            repository_root = Path(authority["repository_root"]).resolve()
            resolved_session_root = self.session_root.resolve(strict=False)
            if (
                resolved_session_root == repository_root
                or resolved_session_root.is_relative_to(repository_root)
            ):
                return self._stopped(
                    "SESSION_LOCATION_INVALID",
                    "session storage must be outside the target repository",
                )
            contract_bytes = Path(authority["contract_path"]).read_bytes()
            contract_buffer_sha256 = hashlib.sha256(
                contract_bytes
            ).hexdigest()
            if not secrets.compare_digest(
                contract_buffer_sha256,
                authority["contract_sha256"],
            ):
                raise ContractParseError(
                    "approved contract changed after authority resolution"
                )
            contract = parse_contract(contract_bytes)
            current_path = (
                Path(authority["selected_root"]) / "current.json"
            )
            current_guard = _guard_path(current_path)
            approval_guard = _guard_path(
                Path(authority["approval_path"])
            )
            if (
                current_guard["sha256"] != authority["current_sha256"]
                or approval_guard["sha256"]
                != authority["approval_sha256"]
            ):
                raise ContractParseError(
                    "authority artifacts changed after resolution"
                )
            ledger_guard = _guard_path(Path(authority["ledger_path"]))
            if ledger_guard["exists"] != authority["ledger_present"]:
                raise ContractParseError(
                    "ledger presence changed after authority resolution"
                )
            report_path = (
                Path(authority["selected_root"])
                / f"v{authority['active_version']}"
                / "check-report.md"
            )
            report_guard = _guard_path(report_path)
            authority_guard = {
                **authority,
                "current_path": str(current_path),
                "report_path": str(report_path),
            }
        except (ContractParseError, KeyError, OSError, ValueError) as error:
            return self._stopped("CONTRACT_INVALID", error)
        try:
            captured = capture_code_evidence(
                authority,
                contract,
                tuple(Path(path) for path in target.narrative_paths),
                self.git_runner,
                self.clock,
                absolute_deadline,
            )
        except (EvidenceError, OSError, ValueError) as error:
            return self._stopped("EVIDENCE_FAILURE", error)
        clauses = [
            {
                "clause_id": clause.clause_id,
                "section": clause.section,
                "text": clause.text,
            }
            for clause in contract.clauses
        ]
        packet = {
            "schema_version": 1,
            "kind": "code",
            "authority": {
                key: authority[key]
                for key in (
                    "active_version",
                    "approval_sha256",
                    "base_sha",
                    "branch",
                    "contract_sha256",
                    "head_sha",
                    "ticket",
                )
            },
            "deadline": {
                "absolute": absolute_deadline,
                "evidence": captured["evidence_deadline"],
            },
            "worktree": captured["worktree"],
            "clauses": clauses,
            "clause_ids": list(contract.clause_ids),
            "changed_paths": captured["changed_paths"],
            "changed_path_ids": [
                item["path_id"] for item in captured["changed_paths"]
            ],
            "evidence": captured["evidence"],
            "evidence_ids": list(captured["evidence"]),
            "reuse_coverage_indeterminate": captured["reuse_truncated"],
        }
        nonce = self.nonce_factory()
        if not isinstance(nonce, str) or not re.fullmatch(
            r"[0-9a-f]{32}", nonce
        ):
            return self._stopped(
                "SESSION_FAILURE",
                "nonce factory returned an invalid nonce",
            )
        state = {
            "schema_version": 1,
            "phase": "code",
            "target": "primary",
            "absolute_deadline": absolute_deadline,
            "nonce": nonce,
            "response_name": f"{self.nonce_factory()}.json",
            "target_identity": {
                "repository_root": str(repository_root),
                "branch": target.branch,
                "ticket": target.ticket,
            },
            "authority_guard": authority_guard,
            "contract_buffer_sha256": contract_buffer_sha256,
            "current_guard": current_guard,
            "approval_guard": approval_guard,
            "ledger_guard": ledger_guard,
            "report_guard": report_guard,
            "deferred_narrative_paths": captured[
                "deferred_narrative_paths"
            ],
            "narrative_guards": [
                _guard_path(repository_root / path)
                for path in captured["deferred_narrative_paths"]
            ],
            "initial_status_bytes_b64": captured[
                "initial_status_bytes_b64"
            ],
            "initial_status_sha256": captured[
                "initial_status_sha256"
            ],
            "recorded_range": {
                "base_sha": authority["base_sha"],
                "head_sha": authority["head_sha"],
            },
            "source_guards": captured["source_guards"],
        }
        try:
            generation = SessionStore(self.session_root).create(state, packet)
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped("SESSION_FAILURE", error)
        return NeedJudgment(
            session=generation.token,
            target="primary",
            kind="code",
            packet_path=generation.packet_path,
            packet_sha256=generation.packet_sha256,
            response_path=generation.response_path,
            next_command=(
                "check-contract-runtime",
                "continue",
                "--session",
                generation.token,
                "--response",
                str(generation.response_path),
            ),
            nonce=nonce,
        )


__all__ = [
    "AuditComplete",
    "AuditDecision",
    "AuditInputError",
    "AuditRuntime",
    "AuditStopped",
    "AuditTarget",
    "AxisItem",
    "ClauseJudgment",
    "CodeJudgment",
    "ContinueAudit",
    "Deviation",
    "DeviationMatch",
    "Finding",
    "LedgerEntry",
    "LocalGitRunner",
    "NeedJudgment",
    "PathAssessment",
    "ReconciliationJudgment",
    "RulePack",
    "SessionIntegrityError",
    "SessionStore",
    "StartAudit",
    "SurfaceJudgment",
    "aggregate",
    "load_rules",
    "validate_code_judgment",
]
