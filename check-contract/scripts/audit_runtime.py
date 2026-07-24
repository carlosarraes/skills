"""Deep public facade for contract-audit policy and runtime orchestration."""

import base64
import hashlib
import json
import math
import os
import re
import secrets
import stat
import sys
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
    REUSE_RESULT_CAP,
    _archive_blobs,
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
    require_exact_keys,
)
from audit_policy import aggregate
from audit_report import (
    ReportError,
    capture_target_state,
    mutation_attestation,
    publish_atomic,
    render_report,
    restore_report,
)
from audit_session import (
    ClaimedResponseError,
    GenerationConsumedError,
    SessionBusyError,
    SessionIntegrityError,
    SessionStore,
)
from audit_validation import validate_code_judgment
from audit_reconciliation import (
    ReconciliationError,
    collect_guarded_narratives,
    qa_head_references,
    read_guarded_bytes,
    reconciliation_response_schema,
)
from probe_runner import ProbeObservation, run_probe


RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "change-contract"
    / "references"
    / "contract-check-rules.json"
)


class _CloseError(RuntimeError):
    def __init__(self, code, reason):
        super().__init__(str(reason))
        self.code = code


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


def _identity_guard_path(path: Path) -> dict[str, object]:
    path = Path(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {
            "path": str(path),
            "exists": False,
            "kind": "absent",
            "dev": None,
            "ino": None,
            "mode": None,
            "size": None,
            "mtime_ns": None,
            "ctime_ns": None,
        }
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

    def _stopped(
        self,
        code,
        reason,
        target="primary",
        *,
        prior_report_preserved=True,
        zero_target_writes=True,
    ):
        return AuditStopped(
            code=code,
            reason=str(reason),
            target=target,
            prior_report_preserved=prior_report_preserved,
            zero_target_writes=zero_target_writes,
        )

    def advance(self, transition):
        if isinstance(transition, ContinueAudit):
            return self._continue(transition)
        if not isinstance(transition, StartAudit):
            return self._stopped(
                "TRANSITION_INVALID",
                "transition must be StartAudit or ContinueAudit",
            )
        if transition.then is None:
            return self._start(transition)
        if not isinstance(transition.primary, AuditTarget):
            return self._stopped(
                "TARGET_INVALID",
                "primary must be an AuditTarget",
            )
        if not isinstance(transition.then, AuditTarget):
            return self._stopped(
                "TARGET_INVALID",
                "then must be an AuditTarget",
                "then",
            )
        if (
            type(transition.deadline_seconds) is not int
            or transition.deadline_seconds <= 0
        ):
            return self._stopped(
                "DEADLINE_INVALID",
                "deadline_seconds must be a positive integer",
            )
        absolute_deadline = self.clock() + min(
            transition.deadline_seconds, 300
        )
        result = self._start(
            transition,
            absolute_deadline=absolute_deadline,
            compound_then=transition.then,
        )
        if not isinstance(result, AuditStopped):
            return result
        if result.code not in {"AUTHORITY_INVALID", "CONTRACT_INVALID"}:
            return result
        closed_target = self._closure_summary(
            outcome="authority-stopped",
            zero_writes=True,
            report_only_write=False,
            prior_report_preserved=True,
            sealed_value={
                "target": self._target_value(transition.primary),
                "terminal_code": result.code,
            },
        )
        then_target = transition.then
        transition = None
        result = None
        try:
            self._seal_initial_closure(
                closed_target,
                absolute_deadline,
            )
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped("SESSION_FAILURE", error)
        return self._start(
            StartAudit(
                primary=then_target,
            ),
            target_name="then",
            absolute_deadline=absolute_deadline,
            closed_target=closed_target,
        )

    @staticmethod
    def _target_value(target):
        return {
            "repo": str(target.repo),
            "branch": target.branch,
            "ticket": target.ticket,
            "narrative_paths": [
                str(path) for path in target.narrative_paths
            ],
        }

    @staticmethod
    def _restore_target(value):
        require_exact_keys(
            value,
            {"repo", "branch", "ticket", "narrative_paths"},
            "compound then target",
        )
        return AuditTarget(
            repo=Path(value["repo"]),
            branch=value["branch"],
            ticket=value["ticket"],
            narrative_paths=tuple(
                Path(path) for path in value["narrative_paths"]
            ),
        )

    def _closure_summary(
        self,
        *,
        outcome,
        zero_writes,
        report_only_write,
        prior_report_preserved,
        sealed_value,
    ):
        public_value = {
            "target": "primary",
            "outcome": outcome,
            "zero_writes": zero_writes,
            "report_only_write": report_only_write,
            "prior_report_preserved": prior_report_preserved,
        }
        digest = hashlib.sha256(
            json.dumps(
                {
                    "summary": public_value,
                    "sealed_target": sealed_value,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
        ).hexdigest()
        return {**public_value, "closure_digest": digest}

    def _closed_state(self, closed_target, absolute_deadline):
        return {
            "schema_version": 1,
            "phase": "closed",
            "target": "primary",
            "absolute_deadline": absolute_deadline,
            "nonce": self._nonce(),
            "response_name": f"{self._nonce()}.json",
            "a_closure_digest": closed_target["closure_digest"],
            "closed_target": dict(closed_target),
        }

    def _seal_initial_closure(self, closed_target, absolute_deadline):
        SessionStore(self.session_root).create(
            self._closed_state(closed_target, absolute_deadline),
            {"schema_version": 1, "kind": "terminal"},
        )

    @staticmethod
    def _next_command(generation):
        return (
            sys.executable,
            str(Path(__file__).resolve().with_name("check_contract.py")),
            "continue",
            "--session",
            generation.token,
            "--response",
            str(generation.response_path),
        )

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

    def _stop_after_claim(
        self,
        store,
        token,
        state,
        code,
        reason,
        lease,
    ):
        try:
            store.tombstone_claimed(
                token,
                self._terminal_state(state, code),
                lease=lease,
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

    def _stop_consumed(self, store, token, state):
        try:
            recovery = store.recover_claim(
                token,
                self._terminal_state(state, "ABANDONED_CLAIM"),
            )
        except SessionBusyError as error:
            return self._stopped(
                "SESSION_BUSY",
                error,
                state.get("target", "session"),
            )
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped(
                "SESSION_INVALID",
                error,
                state.get("target", "session"),
            )
        return self._stopped(
            "DUPLICATE_RESPONSE",
            f"generation was already claimed ({recovery})",
            state.get("target", "session"),
        )

    def _response_envelope(self, raw, token, state):
        def closed_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise AuditInputError(
                        f"response JSON contains duplicate key {key!r}"
                    )
                value[key] = item
            return value

        try:
            value = json.loads(raw, object_pairs_hook=closed_object)
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
        lease,
    ):
        entries, narratives, content_guards = collect_guarded_narratives(
            state
        )
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
        qa_exists, qa_resolution = self._resolve_acceptance_qa(
            narratives,
            state,
        )
        if self.clock() > state["absolute_deadline"]:
            return self._stop_after_claim(
                store,
                token,
                state,
                "DEADLINE_EXPIRED",
                "audit deadline expired during narrative reconciliation",
                lease,
            )
        evidence["runtime:QA-1"] = {
            "acceptance_qa_exists": qa_exists,
            "rule": (
                "guarded supplied/deferred qa-pr marker "
                "and recorded-HEAD heading"
            ),
            "sha_resolution": qa_resolution,
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
            "narrative_content_guards": content_guards,
            "qa_sha_resolution": qa_resolution,
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
                "qa_sha_resolution": qa_resolution,
            },
            "response_schema": reconciliation_response_schema(
                nonce,
                ledger_ids,
                deviation_ids,
                evidence_ids,
                probe_ids,
            ),
        }
        if "a_closure_digest" in state:
            packet["a_closure_digest"] = state["a_closure_digest"]
            packet["closed_target"] = state["closed_target"]
        generation = store.append_claimed(
            token,
            next_state,
            packet,
            lease=lease,
        )
        return NeedJudgment(
            session=generation.token,
            target=state["target"],
            kind="reconciliation",
            packet_path=generation.packet_path,
            packet_sha256=generation.packet_sha256,
            response_path=generation.response_path,
            next_command=self._next_command(generation),
            nonce=nonce,
            a_closure_digest=state.get("a_closure_digest"),
            closed_target=state.get("closed_target"),
        )

    def _resolve_acceptance_qa(self, narratives, state):
        head = state["recorded_range"]["head_sha"]
        candidates = []
        accepted = False
        for reference in qa_head_references(narratives):
            timed_out = False
            truncated = False
            if len(reference) == 40:
                object_ids = [head] if reference == head else []
            else:
                result = self.git_runner.run(
                    ["rev-parse", f"--disambiguate={reference}"],
                    cwd=state["target_identity"]["repository_root"],
                    deadline=state["absolute_deadline"],
                    output_limit=1024 * 1024,
                )
                timed_out = result.timed_out
                truncated = result.truncated
                try:
                    values = result.stdout.decode("ascii").splitlines()
                except UnicodeDecodeError:
                    values = []
                object_ids = sorted(
                    {
                        value
                        for value in values
                        if re.fullmatch(r"[0-9a-f]{40}", value)
                    }
                )
            unique_head = (
                not timed_out
                and not truncated
                and object_ids == [head]
            )
            candidates.append(
                {
                    "reference": reference,
                    "object_ids": object_ids,
                    "timed_out": timed_out,
                    "truncated": truncated,
                    "unique_recorded_head": unique_head,
                }
            )
            accepted = accepted or unique_head
        return accepted, {"candidates": candidates}

    def _restore_code_judgment(self, value):
        return CodeJudgment(
            clauses=tuple(
                ClauseJudgment(**item) for item in value["clauses"]
            ),
            path_assessments=tuple(
                PathAssessment(
                    path_id=item["path_id"],
                    surface=SurfaceJudgment(**item["surface"]),
                    yagni_items=tuple(
                        AxisItem(**axis) for axis in item["yagni_items"]
                    ),
                    reuse_items=tuple(
                        AxisItem(**axis) for axis in item["reuse_items"]
                    ),
                )
                for item in value["path_assessments"]
            ),
            deviations=tuple(
                Deviation(**item) for item in value["deviations"]
            ),
        )

    def _response_evidence(self, value, issued, location, *, optional=False):
        if (
            type(value) is not list
            or any(type(item) is not str or not item for item in value)
            or len(value) != len(set(value))
            or (not optional and not value)
        ):
            raise AuditInputError(
                f"{location} must cite unique issued evidence IDs"
            )
        unknown = sorted(set(value) - issued)
        if unknown:
            raise AuditInputError(
                f"{location} cites evidence outside issued IDs: {unknown}"
            )
        return tuple(value)

    def _validate_reconciliation(self, state, value):
        value = require_exact_keys(
            value,
            {
                "ledger_entries",
                "deviation_matches",
                "contract_obsolete",
                "probe_id",
            },
            "reconciliation judgment",
        )
        issued_evidence = set(state["reconciliation_evidence_ids"])
        issued_ledger = {
            item["ledger_id"]: item for item in state["ledger_entries"]
        }
        ledger_values = value["ledger_entries"]
        if type(ledger_values) is not dict or set(ledger_values) != set(
            issued_ledger
        ):
            raise AuditInputError(
                "reconciliation must contain exactly the issued D IDs"
            )
        details = {}
        for ledger_id in issued_ledger:
            location = f"reconciliation judgment.ledger_entries.{ledger_id}"
            item = require_exact_keys(
                ledger_values[ledger_id],
                {"status", "evidence_ids", "reason"},
                location,
            )
            if item["status"] not in {
                "VERIFIED",
                "QUESTIONABLE",
                "CONTRADICTED",
            }:
                raise AuditInputError(
                    f"{location}.status is not a closed enum value"
                )
            reason = item["reason"]
            if not isinstance(reason, str) or not reason.strip():
                raise AuditInputError(f"{location}.reason must be non-empty")
            details[ledger_id] = {
                "status": item["status"],
                "evidence_ids": self._response_evidence(
                    item["evidence_ids"],
                    issued_evidence,
                    f"{location}.evidence_ids",
                ),
                "reason": reason.strip(),
            }
        raw_matches = value["deviation_matches"]
        if type(raw_matches) is not list:
            raise AuditInputError(
                "reconciliation judgment.deviation_matches must be a list"
            )
        deviation_ids = {
            item["deviation_id"] for item in state["code_judgment"]["deviations"]
        }
        matches = []
        matched = set()
        for index, raw in enumerate(raw_matches):
            match = require_exact_keys(
                raw,
                {"deviation_id", "ledger_id"},
                f"reconciliation judgment.deviation_matches[{index}]",
            )
            deviation_id = match["deviation_id"]
            ledger_id = match["ledger_id"]
            if deviation_id not in deviation_ids:
                raise AuditInputError(
                    "deviation match cites an unissued deviation ID"
                )
            if ledger_id not in issued_ledger:
                raise AuditInputError(
                    "deviation match cites an unissued ledger ID"
                )
            if deviation_id in matched:
                raise AuditInputError(
                    "deviation match duplicates a deviation ID"
                )
            matched.add(deviation_id)
            matches.append(DeviationMatch(deviation_id, ledger_id))
        obsolete = require_exact_keys(
            value["contract_obsolete"],
            {"value", "evidence_ids", "reason"},
            "reconciliation judgment.contract_obsolete",
        )
        if type(obsolete["value"]) is not bool:
            raise AuditInputError("contract_obsolete.value must be boolean")
        reason = obsolete["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise AuditInputError("contract_obsolete.reason must be non-empty")
        obsolete_evidence = self._response_evidence(
            obsolete["evidence_ids"],
            issued_evidence,
            "contract_obsolete.evidence_ids",
            optional=not obsolete["value"],
        )
        probe_id = value["probe_id"]
        if probe_id is not None and (
            type(probe_id) is not str
            or probe_id not in state["issued_probes"]
        ):
            raise AuditInputError(
                "probe_id must be null or one runtime-issued probe ID"
            )
        return {
            "ledger_entries": details,
            "deviation_matches": tuple(matches),
            "contract_obsolete": obsolete["value"],
            "contract_obsolete_evidence_ids": obsolete_evidence,
            "contract_obsolete_reason": reason.strip(),
            "probe_id": probe_id,
        }

    def _execute_probe(self, state, probe_id):
        if probe_id is None:
            return None
        try:
            return run_probe(
                probe_id=probe_id,
                descriptor=state["issued_probes"][probe_id],
                repository_root=Path(
                    state["target_identity"]["repository_root"]
                ),
                recorded_head=state["recorded_range"]["head_sha"],
                disposable_root=self.session_root,
                git_runner=self.git_runner,
                clock=self.clock,
                absolute_deadline=state["absolute_deadline"],
            )
        except (EvidenceError, OSError, TypeError, ValueError) as error:
            return ProbeObservation(
                probe_id=probe_id,
                success=False,
                timed_out=False,
                exit_code=None,
                reason="probe execution failed before observation",
            )

    def _effective_reconciliation(self, state, details, observation):
        selected = details["probe_id"]
        effective = []
        for issued in state["ledger_entries"]:
            ledger_id = issued["ledger_id"]
            status = details["ledger_entries"][ledger_id]["status"]
            required_probe = issued["probe_id"]
            if required_probe is not None and status == "VERIFIED":
                probe_verified = (
                    selected == required_probe
                    and observation is not None
                    and observation.success
                )
                if not probe_verified:
                    status = "QUESTIONABLE"
            effective.append(LedgerEntry(ledger_id, status))
        details["effective_ledger_entries"] = tuple(effective)
        return ReconciliationJudgment(
            ledger_entries=tuple(effective),
            deviation_matches=details["deviation_matches"],
            contract_obsolete=details["contract_obsolete"],
            acceptance_qa_exists=state["acceptance_qa_exists"],
        )

    def _git_bytes(
        self,
        args,
        state,
        operation,
        *,
        output_limit=None,
        allow_truncated=False,
    ):
        result = self.git_runner.run(
            args,
            cwd=state["target_identity"]["repository_root"],
            deadline=state["absolute_deadline"],
            output_limit=output_limit,
        )
        if result.timed_out:
            raise _CloseError(
                "FRESHNESS_FAILED",
                f"{operation} timed out during final freshness",
            )
        if result.truncated and not allow_truncated:
            raise _CloseError(
                "FRESHNESS_FAILED",
                f"{operation} was truncated during final freshness",
            )
        return result

    def _require_content_guard(self, expected):
        identity = {
            key: value for key, value in expected.items() if key != "sha256"
        }
        try:
            content, actual = read_guarded_bytes(identity)
        except ReconciliationError as error:
            raise _CloseError("FRESHNESS_FAILED", error) from error
        if actual != expected:
            raise _CloseError(
                "FRESHNESS_FAILED",
                f"guarded narrative changed: {expected['path']}",
            )
        return content

    def _verify_source_guards(self, state):
        guards = state["source_guards"]
        inputs = state["source_guard_inputs"]
        base = guards["base_sha"]
        head = guards["head_sha"]
        inventory = self._git_bytes(
            ["diff", "--name-status", "--find-renames", "-z", f"{base}..{head}"],
            state,
            "source inventory",
        ).stdout
        if hashlib.sha256(inventory).hexdigest() != guards[
            "inventory_sha256"
        ]:
            raise _CloseError(
                "FRESHNESS_FAILED", "source inventory guard changed"
            )
        diff_args = [
            "diff",
            "--find-renames",
            "--no-ext-diff",
            f"{base}..{head}",
            "--",
            *inputs["changed_paths"],
        ]
        diff = (
            self._git_bytes(diff_args, state, "source diff").stdout
            if inputs["changed_paths"]
            else b""
        )
        if hashlib.sha256(diff).hexdigest() != guards["diff_sha256"]:
            raise _CloseError("FRESHNESS_FAILED", "source diff guard changed")
        if inputs["head_paths"]:
            archive = self._git_bytes(
                [
                    "archive",
                    "--format=tar",
                    head,
                    "--",
                    *inputs["head_paths"],
                ],
                state,
                "source archive",
            ).stdout
            try:
                _, blob_guards = _archive_blobs(
                    archive, inputs["head_paths"]
                )
            except EvidenceError as error:
                raise _CloseError("FRESHNESS_FAILED", error) from error
        else:
            blob_guards = {}
        if blob_guards != guards["head_blob_sha256"]:
            raise _CloseError("FRESHNESS_FAILED", "source blob guards changed")
        tree = self._git_bytes(
            ["ls-tree", "-r", "-z", "--name-only", head],
            state,
            "source tree",
        ).stdout
        if hashlib.sha256(tree).hexdigest() != guards["tree_paths_sha256"]:
            raise _CloseError("FRESHNESS_FAILED", "source tree guard changed")
        grep_args = ["grep", "-n", "-I", "-F", "-z"]
        for token in inputs["reuse_query"]:
            grep_args.extend(("-e", token))
        grep_args.extend((head, "--"))
        reuse = self._git_bytes(
            grep_args,
            state,
            "reuse search",
            output_limit=REUSE_RESULT_CAP,
            allow_truncated=True,
        )
        if (
            reuse.truncated != inputs["reuse_truncated"]
            or hashlib.sha256(reuse.stdout).hexdigest()
            != guards["reuse_result_sha256"]
        ):
            raise _CloseError(
                "FRESHNESS_FAILED", "reuse evidence guard changed"
            )

    def _verify_freshness(self, state):
        if self.clock() > state["absolute_deadline"]:
            raise _CloseError(
                "DEADLINE_EXPIRED",
                "audit deadline expired before final freshness",
            )
        repo = Path(state["target_identity"]["repository_root"])
        try:
            authority = self.authority_resolver(
                repo,
                state["target_identity"]["branch"],
                state["target_identity"]["ticket"],
            )
        except (AuthorityError, OSError, ValueError) as error:
            raise _CloseError("FRESHNESS_FAILED", error) from error
        current_path = Path(authority["selected_root"]) / "current.json"
        report_path = (
            Path(authority["selected_root"])
            / f"v{authority['active_version']}"
            / "check-report.md"
        )
        fresh_authority = {
            **authority,
            "current_path": str(current_path),
            "report_path": str(report_path),
        }
        if fresh_authority != state["authority_guard"]:
            raise _CloseError(
                "FRESHNESS_FAILED", "approved authority changed"
            )
        head = self._git_bytes(
            ["rev-parse", "--verify", "HEAD"],
            state,
            "HEAD",
        ).stdout.decode("ascii", "strict").strip()
        if head != state["recorded_range"]["head_sha"]:
            raise _CloseError("FRESHNESS_FAILED", "HEAD changed")
        contract_path = Path(authority["contract_path"])
        if _guard_path(contract_path)["sha256"] != state[
            "contract_buffer_sha256"
        ]:
            raise _CloseError(
                "FRESHNESS_FAILED", "approved contract bytes changed"
            )
        if _guard_path(current_path) != state["current_guard"]:
            raise _CloseError(
                "FRESHNESS_FAILED", "current authority pointer changed"
            )
        if _guard_path(Path(authority["approval_path"])) != state[
            "approval_guard"
        ]:
            raise _CloseError(
                "FRESHNESS_FAILED", "approval artifact changed"
            )
        content_guards = state["narrative_content_guards"]
        self._require_content_guard(content_guards["ledger"])
        prior_report = self._require_content_guard(content_guards["report"])
        for guard in content_guards["narratives"]:
            self._require_content_guard(guard)
        status = self._git_bytes(
            ["status", "--porcelain=v1", "--untracked-files=all"],
            state,
            "worktree status",
        ).stdout
        if status != base64.b64decode(state["initial_status_bytes_b64"]):
            raise _CloseError(
                "FRESHNESS_FAILED", "worktree status changed"
            )
        self._verify_source_guards(state)
        if self.clock() > state["absolute_deadline"]:
            raise _CloseError(
                "DEADLINE_EXPIRED",
                "audit deadline expired during final freshness",
            )
        return report_path, prior_report

    def _close_reconciliation(self, state, packet, judgment_value):
        repository_root = Path(
            state["target_identity"]["repository_root"]
        )
        initial_target_state = capture_target_state(repository_root)
        details = self._validate_reconciliation(state, judgment_value)
        observation = self._execute_probe(state, details["probe_id"])
        code = self._restore_code_judgment(state["code_judgment"])
        reconciliation = self._effective_reconciliation(
            state, details, observation
        )
        decision = aggregate(code, reconciliation, load_rules(RULES_PATH))
        report_relative = Path(
            state["authority_guard"]["report_path"]
        ).relative_to(repository_root).as_posix()
        report = render_report(
            authority=state["authority_guard"],
            worktree_status=state["worktree_status"],
            code_judgment=code,
            reconciliation_details=details,
            decision=decision,
            probe_observation=observation,
            report_relative_path=report_relative,
        )
        report_path, prior_report = self._verify_freshness(state)
        if capture_target_state(repository_root) != initial_target_state:
            raise _CloseError(
                "MUTATION_DETECTED",
                "target mutation detected before report publication",
            )
        if self.clock() > state["absolute_deadline"]:
            raise _CloseError(
                "DEADLINE_EXPIRED",
                "audit deadline expired before report publication",
            )
        try:
            report_sha256 = publish_atomic(report_path, report)
            after = capture_target_state(repository_root)
            attestation = mutation_attestation(
                initial_target_state, after, report_relative
            )
            if not attestation["only_active_report_changed"]:
                raise ReportError(
                    "final target mutation set is not the active report only"
                )
        except BaseException as error:
            current = (
                report_path.read_bytes() if report_path.exists() else None
            )
            if current != prior_report:
                restore_report(report_path, prior_report)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(error, ReportError):
                raise
            raise ReportError(
                f"report attestation failed: {type(error).__name__}"
            ) from error
        return AuditComplete(
            verdict=decision.verdict,
            route=decision.route,
            report_path=report_path,
            report_sha256=report_sha256,
            mutation_attestation=attestation,
        )

    def _continue(self, request):
        store = SessionStore(self.session_root)
        lease = None
        try:
            state = store.load(request.session)
            packet = store.load_packet(request.session)
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped("SESSION_INVALID", error, "session")
        try:
            if state["phase"] not in {"code", "reconciliation"}:
                try:
                    lease = store.claim_lease(request.session)
                except GenerationConsumedError:
                    return self._stop_consumed(
                        store,
                        request.session,
                        state,
                    )
                except SessionBusyError as error:
                    return self._stopped(
                        "SESSION_BUSY",
                        error,
                        state.get("target", "session"),
                    )
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
                    "generation is not in an open judgment phase",
                    lease,
                )
            response_absent = not os.path.lexists(request.response_path)
            try:
                lease, raw = store.claim_and_read(
                    request.session,
                    request.response_path,
                )
            except GenerationConsumedError:
                return self._stop_consumed(
                    store,
                    request.session,
                    state,
                )
            except ClaimedResponseError as error:
                lease = error.lease
                code = (
                    "OUT_OF_PHASE"
                    if state["phase"] == "reconciliation"
                    and response_absent
                    else "RESPONSE_INVALID"
                )
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    code,
                    error,
                    lease,
                )
            except SessionBusyError as error:
                return self._stopped(
                    "SESSION_BUSY",
                    error,
                    state.get("target", "session"),
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
                    lease,
                )
            try:
                judgment_value = self._response_envelope(
                    raw,
                    request.session,
                    state,
                )
                if state["phase"] == "reconciliation":
                    completion = self._close_reconciliation(
                        state,
                        packet,
                        judgment_value,
                    )
                    then_value = state.get("compound_then")
                    if then_value is None:
                        return completion
                    closed_target = self._closure_summary(
                        outcome="closed",
                        zero_writes=False,
                        report_only_write=bool(
                            completion.mutation_attestation[
                                "only_active_report_changed"
                            ]
                        ),
                        prior_report_preserved=not bool(
                            state["report_guard"]["exists"]
                        ),
                        sealed_value={
                            "state": {
                                key: value
                                for key, value in state.items()
                                if key != "compound_then"
                            },
                            "verdict": completion.verdict,
                            "route": list(completion.route),
                            "report_sha256": (
                                completion.report_sha256
                            ),
                            "mutation_attestation": dict(
                                completion.mutation_attestation
                            ),
                        },
                    )
                    then_target = self._restore_target(then_value)
                    absolute_deadline = state["absolute_deadline"]
                    store.tombstone_claimed(
                        request.session,
                        self._closed_state(
                            closed_target,
                            absolute_deadline,
                        ),
                        lease=lease,
                    )
                    lease.close()
                    lease = None
                    state = None
                    packet = None
                    judgment_value = None
                    completion = None
                    request = None
                    return self._start(
                        StartAudit(primary=then_target),
                        target_name="then",
                        absolute_deadline=absolute_deadline,
                        closed_target=closed_target,
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
                    lease,
                )
            except _CloseError as error:
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    error.code,
                    error,
                    lease,
                )
            except ReportError as error:
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    "PUBLICATION_FAILED",
                    error,
                    lease,
                )
            except (AuthorityError, ContractParseError) as error:
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    "FRESHNESS_FAILED",
                    error,
                    lease,
                )
            try:
                return self._issue_reconciliation(
                    store,
                    request.session,
                    state,
                    packet,
                    code_judgment,
                    lease,
                )
            except ReconciliationError as error:
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    "NARRATIVE_INVALID",
                    error,
                    lease,
                )
            except EvidenceError as error:
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    "EVIDENCE_FAILURE",
                    error,
                    lease,
                )
            except (SessionIntegrityError, OSError, ValueError) as error:
                return self._stop_after_claim(
                    store,
                    request.session,
                    state,
                    "SESSION_FAILURE",
                    error,
                    lease,
                )
        finally:
            if lease is not None:
                lease.close()

    def _start(
        self,
        request: StartAudit,
        *,
        target_name="primary",
        absolute_deadline=None,
        compound_then=None,
        closed_target=None,
    ):
        target = request.primary
        if not isinstance(target, AuditTarget):
            return self._stopped(
                "TARGET_INVALID",
                "primary must be an AuditTarget",
                target_name,
            )
        if (
            type(request.deadline_seconds) is not int
            or request.deadline_seconds <= 0
        ):
            return self._stopped(
                "DEADLINE_INVALID",
                "deadline_seconds must be a positive integer",
                target_name,
            )
        if absolute_deadline is None:
            absolute_deadline = self.clock() + min(
                request.deadline_seconds, 300
            )
        if self.clock() > absolute_deadline:
            return self._stopped(
                "DEADLINE_EXPIRED",
                "audit deadline expired before target start",
                target_name,
            )
        try:
            authority = self.authority_resolver(
                Path(target.repo),
                target.branch,
                target.ticket,
            )
        except (AuthorityError, OSError, ValueError) as error:
            return self._stopped("AUTHORITY_INVALID", error, target_name)
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
                    target_name,
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
            ledger_guard = _identity_guard_path(
                Path(authority["ledger_path"])
            )
            if ledger_guard["exists"] != authority["ledger_present"]:
                raise ContractParseError(
                    "ledger presence changed after authority resolution"
                )
            report_path = (
                Path(authority["selected_root"])
                / f"v{authority['active_version']}"
                / "check-report.md"
            )
            report_guard = _identity_guard_path(report_path)
            authority_guard = {
                **authority,
                "current_path": str(current_path),
                "report_path": str(report_path),
            }
        except (ContractParseError, KeyError, OSError, ValueError) as error:
            return self._stopped("CONTRACT_INVALID", error, target_name)
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
            return self._stopped("EVIDENCE_FAILURE", error, target_name)
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
        if closed_target is not None:
            packet["a_closure_digest"] = closed_target["closure_digest"]
            packet["closed_target"] = dict(closed_target)
        try:
            nonce = self._nonce()
            response_name = f"{self._nonce()}.json"
        except SessionIntegrityError as error:
            return self._stopped(
                "SESSION_FAILURE",
                error,
                target_name,
            )
        state = {
            "schema_version": 1,
            "phase": "code",
            "target": target_name,
            "absolute_deadline": absolute_deadline,
            "nonce": nonce,
            "response_name": response_name,
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
                _identity_guard_path(repository_root / path)
                for path in captured["deferred_narrative_paths"]
            ],
            "initial_status_bytes_b64": captured[
                "initial_status_bytes_b64"
            ],
            "initial_status_sha256": captured[
                "initial_status_sha256"
            ],
            "worktree_status": captured["worktree"]["status"],
            "recorded_range": {
                "base_sha": authority["base_sha"],
                "head_sha": authority["head_sha"],
            },
            "source_guards": captured["source_guards"],
            "source_guard_inputs": {
                "changed_paths": [
                    item["path"] for item in captured["changed_paths"]
                ],
                "head_paths": [
                    item["path"]
                    for item in captured["changed_paths"]
                    if not item["status"].startswith("D")
                ],
                "reuse_query": captured["evidence"][
                    "reuse:SEARCH-1"
                ]["query"],
                "reuse_truncated": captured["reuse_truncated"],
            },
        }
        if compound_then is not None:
            state["compound_then"] = self._target_value(compound_then)
        if closed_target is not None:
            state["a_closure_digest"] = closed_target["closure_digest"]
            state["closed_target"] = dict(closed_target)
        try:
            generation = SessionStore(self.session_root).create(state, packet)
        except (SessionIntegrityError, OSError, ValueError) as error:
            return self._stopped("SESSION_FAILURE", error, target_name)
        return NeedJudgment(
            session=generation.token,
            target=target_name,
            kind="code",
            packet_path=generation.packet_path,
            packet_sha256=generation.packet_sha256,
            response_path=generation.response_path,
            next_command=self._next_command(generation),
            nonce=nonce,
            a_closure_digest=(
                closed_target["closure_digest"]
                if closed_target is not None
                else None
            ),
            closed_target=closed_target,
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
