"""Immutable contract-audit domain types and strict v1 rule loading."""

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
STATUS_VALUES = {
    "clause": ("MET", "UNMET", "EXCEEDED", "INDETERMINATE"),
    "ledger": ("VERIFIED", "QUESTIONABLE", "CONTRADICTED"),
    "fidelity": ("PASS", "PARTIAL", "FAIL"),
    "yagni": ("PASS", "WARNING", "FAIL"),
    "reuse": ("PASS", "WARNING", "FAIL"),
    "documented_drift": ("NONE", "ACCEPTED", "QUESTIONABLE"),
    "undocumented_drift": ("NONE", "PRESENT"),
}
FIDELITY_FAMILIES = ("O", "B", "N", "I", "C", "A")
FIDELITY_EVIDENCE_NAMESPACES = (
    "behavior",
    "public-contract",
    "risk",
    "acceptance",
)
PRECEDENCE = (
    "CONTRACT_OBSOLETE",
    "FIDELITY_FAIL_WITH_SIMPLICITY",
    "FIDELITY_FAIL",
    "UNRESOLVED_WITH_SIMPLICITY",
    "UNRESOLVED",
    "SIMPLICITY_ONLY",
    "PASS_WITH_DOCUMENTED_DRIFT",
    "PASS",
)
ROUTES = {
    "CONTRACT_OBSOLETE": ("change-contract",),
    "FIDELITY_FAIL_WITH_SIMPLICITY": ("exec-ticket", "clean-up"),
    "FIDELITY_FAIL": ("exec-ticket",),
    "UNRESOLVED_WITH_SIMPLICITY": ("clean-up",),
    "UNRESOLVED": ("qa-ticket",),
    "SIMPLICITY_ONLY": ("clean-up",),
    "PASS_WITH_DOCUMENTED_DRIFT": {
        "acceptance_qa_exists": ("qa-pr",),
        "otherwise": ("qa-ticket",),
    },
    "PASS": {
        "acceptance_qa_exists": ("qa-pr",),
        "otherwise": ("qa-ticket",),
    },
}
_RULE_KEYS = {
    "schema_version",
    "statuses",
    "fidelity_families",
    "fidelity_evidence_namespaces",
    "precedence",
    "routes",
    "report_schema_version",
}


class AuditInputError(ValueError):
    """Raised when an input violates the closed audit policy schema."""


@dataclass(frozen=True)
class RulePack:
    schema_version: int
    statuses: Mapping[str, tuple[str, ...]]
    fidelity_families: tuple[str, ...]
    fidelity_evidence_namespaces: tuple[str, ...]
    precedence: tuple[str, ...]
    routes: Mapping[str, object]
    report_schema_version: int


@dataclass(frozen=True)
class ClauseJudgment:
    clause_id: str
    status: str
    evidence_ids: tuple[str, ...]
    reason: str
    contract_boundary_changed: bool


@dataclass(frozen=True)
class AxisItem:
    item_id: str
    kind: str
    evidence_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SurfaceJudgment:
    status: str
    evidence_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class PathAssessment:
    path_id: str
    surface: SurfaceJudgment
    yagni_items: tuple[AxisItem, ...]
    reuse_items: tuple[AxisItem, ...]


@dataclass(frozen=True)
class Deviation:
    deviation_id: str
    source_kind: str
    source_id: str
    path_id: str
    line: int
    description: str
    evidence_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class CodeJudgment:
    clauses: tuple[ClauseJudgment, ...]
    path_assessments: tuple[PathAssessment, ...]
    deviations: tuple[Deviation, ...]


@dataclass(frozen=True)
class LedgerEntry:
    ledger_id: str
    status: str


@dataclass(frozen=True)
class DeviationMatch:
    deviation_id: str
    ledger_id: str


@dataclass(frozen=True)
class ReconciliationJudgment:
    ledger_entries: tuple[LedgerEntry, ...]
    deviation_matches: tuple[DeviationMatch, ...]
    contract_obsolete: bool
    acceptance_qa_exists: bool


@dataclass(frozen=True)
class Finding:
    finding_id: str
    condition: str
    source_kind: str
    source_id: str
    path_id: str
    line: int
    reason: str
    sort_key: tuple[int, str, str, int, str]


@dataclass(frozen=True)
class AuditDecision:
    fidelity: str
    yagni: str
    reuse: str
    documented_drift: str
    undocumented_drift: str
    verdict: str
    route: tuple[str, ...]
    findings: tuple[Finding, ...]

    @property
    def finding_ids(self):
        return tuple(item.finding_id for item in self.findings)


def clause_family(clause_id):
    return "A" if clause_id.startswith("A-") else clause_id.split("-", 1)[0][0]


def require_object(value, location):
    if not isinstance(value, dict):
        raise AuditInputError(f"{location} must be a JSON object")
    return value


def require_exact_keys(value, expected, location):
    obj = require_object(value, location)
    actual = set(obj)
    expected = set(expected)
    if actual != expected:
        raise AuditInputError(
            f"{location} has extra JSON keys {sorted(actual - expected)} "
            f"or missing JSON keys {sorted(expected - actual)}"
        )
    return obj


def _string_list(value, location):
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise AuditInputError(
            f"{location} must be a unique list of non-empty strings"
        )
    return tuple(value)


def _validate_versions(document):
    for field, expected in (
        ("schema_version", SCHEMA_VERSION),
        ("report_schema_version", REPORT_SCHEMA_VERSION),
    ):
        if type(document[field]) is not int or document[field] != expected:
            raise AuditInputError(f"{field} must be exactly version 1")


def _validate_statuses(value):
    value = require_exact_keys(value, STATUS_VALUES, "statuses")
    actual = {
        name: _string_list(value[name], f"statuses.{name}")
        for name in STATUS_VALUES
    }
    if actual != STATUS_VALUES:
        raise AuditInputError("statuses do not match the closed v1 values")
    return MappingProxyType(actual)


def _validate_routes(value):
    value = require_exact_keys(value, ROUTES, "routes")
    frozen = {}
    for name, expected in ROUTES.items():
        actual = value[name]
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                raise AuditInputError(
                    f"routes.{name} must use the conditional v1 shape"
                )
            actual = require_exact_keys(
                actual,
                {"acceptance_qa_exists", "otherwise"},
                f"routes.{name}",
            )
            route = {
                key: _string_list(actual[key], f"routes.{name}.{key}")
                for key in ("acceptance_qa_exists", "otherwise")
            }
            if route != expected:
                raise AuditInputError(
                    f"routes.{name} does not match the closed v1 policy"
                )
            frozen[name] = MappingProxyType(route)
        else:
            if not isinstance(actual, list):
                raise AuditInputError(
                    f"routes.{name} must use the fixed v1 shape"
                )
            route = _string_list(actual, f"routes.{name}")
            if route != expected:
                raise AuditInputError(
                    f"routes.{name} does not match the closed v1 policy"
                )
            frozen[name] = route
    return MappingProxyType(frozen)


def load_rules(path: Path) -> RulePack:
    """Load only the canonical closed v1 policy shape."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditInputError(f"cannot load rule pack: {error}") from error
    document = require_exact_keys(document, _RULE_KEYS, "rule pack")
    _validate_versions(document)
    statuses = _validate_statuses(document["statuses"])
    fidelity_families = _string_list(
        document["fidelity_families"], "fidelity_families"
    )
    if fidelity_families != FIDELITY_FAMILIES:
        raise AuditInputError("fidelity_families do not match closed v1")
    namespaces = _string_list(
        document["fidelity_evidence_namespaces"],
        "fidelity_evidence_namespaces",
    )
    if namespaces != FIDELITY_EVIDENCE_NAMESPACES:
        raise AuditInputError(
            "fidelity_evidence_namespaces do not match closed v1"
        )
    precedence = _string_list(document["precedence"], "precedence")
    if precedence != PRECEDENCE:
        raise AuditInputError("precedence does not match closed v1")
    return RulePack(
        schema_version=SCHEMA_VERSION,
        statuses=statuses,
        fidelity_families=fidelity_families,
        fidelity_evidence_namespaces=namespaces,
        precedence=precedence,
        routes=_validate_routes(document["routes"]),
        report_schema_version=REPORT_SCHEMA_VERSION,
    )
