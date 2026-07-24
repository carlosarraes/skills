"""Deep public facade for contract-audit policy and runtime orchestration."""

import hashlib
import os
import re
import secrets
import stat
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
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
    SessionIntegrityError,
    SessionStore,
)
from audit_validation import validate_code_judgment


def _deep_freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


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
            return self._stopped(
                "CONTINUE_UNAVAILABLE",
                "audit continuation is deferred to the next runtime task",
                "session",
            )
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
