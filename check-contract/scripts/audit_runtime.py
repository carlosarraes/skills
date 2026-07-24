"""Pure validation and aggregation policy for deterministic contract audits."""

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


_RULE_KEYS = {
    "schema_version",
    "statuses",
    "fidelity_families",
    "fidelity_evidence_namespaces",
    "precedence",
    "routes",
    "report_schema_version",
}
_STATUS_KEYS = {
    "clause",
    "ledger",
    "fidelity",
    "yagni",
    "reuse",
    "documented_drift",
    "undocumented_drift",
}
_PRECEDENCE = (
    "CONTRACT_OBSOLETE",
    "FIDELITY_FAIL_WITH_SIMPLICITY",
    "FIDELITY_FAIL",
    "UNRESOLVED_WITH_SIMPLICITY",
    "UNRESOLVED",
    "SIMPLICITY_ONLY",
    "PASS_WITH_DOCUMENTED_DRIFT",
    "PASS",
)
_YAGNI_KINDS = frozenset(
    {
        "UNEARNED_LOCAL",
        "UNEARNED_MODULE",
        "UNEARNED_RUNTIME_DEPENDENCY",
        "UNEARNED_CONFIGURATION",
        "UNEARNED_PUBLIC_INTERFACE",
        "QUESTIONABLE_LOCAL",
        "QUESTIONABLE_OTHER",
    }
)
_STRUCTURAL_YAGNI_KINDS = frozenset(
    {
        "UNEARNED_MODULE",
        "UNEARNED_RUNTIME_DEPENDENCY",
        "UNEARNED_CONFIGURATION",
        "UNEARNED_PUBLIC_INTERFACE",
    }
)
_REUSE_KINDS = frozenset(
    {
        "REUSED",
        "NO_REUSE_AVAILABLE",
        "DUPLICATED",
        "BYPASSED",
        "NEAR_DUPLICATE",
        "INDETERMINATE",
    }
)
_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "change-contract"
    / "references"
    / "contract-check-rules.json"
)


class AuditInputError(ValueError):
    """Raised when policy input violates a closed runtime-owned schema."""


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
class AuditDecision:
    fidelity: str
    yagni: str
    reuse: str
    documented_drift: str
    undocumented_drift: str
    verdict: str
    route: tuple[str, ...]
    finding_ids: tuple[str, ...]


def _require_object(value, location):
    if not isinstance(value, dict):
        raise AuditInputError(f"{location} must be a JSON object")
    return value


def _require_exact_keys(value, expected, location):
    obj = _require_object(value, location)
    actual = set(obj)
    expected = set(expected)
    if actual != expected:
        extras = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise AuditInputError(
            f"{location} has extra JSON keys {extras} or missing JSON keys "
            f"{missing}"
        )
    return obj


def _closed_string_list(value, location):
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != len(value)
    ):
        raise AuditInputError(
            f"{location} must be a unique list of non-empty strings"
        )
    return tuple(value)


def _positive_schema_version(value, location):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AuditInputError(f"{location} must be a positive integer")
    return value


def _freeze_route(value, location):
    if isinstance(value, list):
        return _closed_string_list(value, location)
    obj = _require_exact_keys(
        value, {"acceptance_qa_exists", "otherwise"}, location
    )
    return MappingProxyType(
        {
            key: _closed_string_list(obj[key], f"{location}.{key}")
            for key in ("acceptance_qa_exists", "otherwise")
        }
    )


def load_rules(path: Path) -> RulePack:
    """Load and strictly validate the canonical executable rule pack."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditInputError(f"cannot load rule pack: {error}") from error
    document = _require_exact_keys(document, _RULE_KEYS, "rule pack")
    statuses = _require_exact_keys(
        document["statuses"], _STATUS_KEYS, "rule pack.statuses"
    )
    frozen_statuses = MappingProxyType(
        {
            name: _closed_string_list(
                statuses[name], f"rule pack.statuses.{name}"
            )
            for name in sorted(_STATUS_KEYS)
        }
    )
    precedence = _closed_string_list(
        document["precedence"], "rule pack.precedence"
    )
    if precedence != _PRECEDENCE:
        raise AuditInputError("rule pack.precedence is not the closed order")
    routes = _require_exact_keys(
        document["routes"], precedence, "rule pack.routes"
    )
    frozen_routes = MappingProxyType(
        {
            name: _freeze_route(routes[name], f"rule pack.routes.{name}")
            for name in precedence
        }
    )
    return RulePack(
        schema_version=_positive_schema_version(
            document["schema_version"], "rule pack.schema_version"
        ),
        statuses=frozen_statuses,
        fidelity_families=_closed_string_list(
            document["fidelity_families"],
            "rule pack.fidelity_families",
        ),
        fidelity_evidence_namespaces=_closed_string_list(
            document["fidelity_evidence_namespaces"],
            "rule pack.fidelity_evidence_namespaces",
        ),
        precedence=precedence,
        routes=frozen_routes,
        report_schema_version=_positive_schema_version(
            document["report_schema_version"],
            "rule pack.report_schema_version",
        ),
    )


def _runtime_ids(packet, key, label):
    packet = _require_object(packet, "packet")
    if key not in packet:
        raise AuditInputError(f"packet is missing {label}")
    values = packet[key]
    if (
        not isinstance(values, list)
        or any(not isinstance(item, str) or not item for item in values)
        or len(values) != len(set(values))
    ):
        raise AuditInputError(f"packet {label} must be unique strings")
    return tuple(values)


def _non_empty_text(value, location, label="non-empty reason"):
    if not isinstance(value, str) or not value.strip():
        raise AuditInputError(f"{location} requires {label} text")
    return value.strip()


def _evidence_ids(value, issued, location, allowed_namespaces=None):
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise AuditInputError(
            f"{location} issued evidence IDs must be a unique string list"
        )
    unknown = sorted(set(value) - issued)
    if unknown:
        raise AuditInputError(
            f"{location} cites evidence outside the issued evidence IDs: "
            f"{unknown}"
        )
    if allowed_namespaces is not None:
        invalid = sorted(
            evidence_id
            for evidence_id in value
            if evidence_id.partition(":")[0] not in allowed_namespaces
        )
        if invalid:
            raise AuditInputError(
                f"{location} violates fidelity evidence namespace ownership: "
                f"{invalid}"
            )
    return tuple(value)


def _clause_family(clause_id):
    return "A" if clause_id.startswith("A-") else clause_id.partition("-")[0][0]


def _parse_axis_item(value, issued, location, allowed_kinds):
    value = _require_exact_keys(
        value, {"kind", "evidence_ids", "reason"}, location
    )
    kind = value["kind"]
    if kind not in allowed_kinds:
        raise AuditInputError(
            f"{location}.kind is not a closed enum value: {kind!r}"
        )
    return AxisItem(
        kind=kind,
        evidence_ids=_evidence_ids(
            value["evidence_ids"], issued, f"{location}.evidence_ids"
        ),
        reason=_non_empty_text(value["reason"], location),
    )


def validate_code_judgment(packet, response) -> CodeJudgment:
    """Validate one model response against runtime-issued IDs and enums."""
    rules = load_rules(_DEFAULT_RULES_PATH)
    clause_ids = _runtime_ids(packet, "clause_ids", "clause IDs")
    path_ids = _runtime_ids(packet, "changed_path_ids", "changed-path IDs")
    issued_evidence = set(
        _runtime_ids(packet, "evidence_ids", "issued evidence IDs")
    )
    response = _require_exact_keys(
        response,
        {"clauses", "path_assessments", "deviations"},
        "code judgment",
    )
    clauses = _require_object(response["clauses"], "code judgment.clauses")
    if set(clauses) != set(clause_ids) or len(clauses) != len(clause_ids):
        raise AuditInputError(
            "code judgment must contain exactly the runtime-issued clause IDs"
        )
    parsed_clauses = []
    clause_statuses = set(rules.statuses["clause"])
    fidelity_families = set(rules.fidelity_families)
    fidelity_namespaces = set(rules.fidelity_evidence_namespaces)
    for clause_id in clause_ids:
        location = f"code judgment.clauses.{clause_id}"
        value = _require_exact_keys(
            clauses[clause_id],
            {
                "status",
                "evidence_ids",
                "reason",
                "contract_boundary_changed",
            },
            location,
        )
        status = value["status"]
        if status not in clause_statuses:
            raise AuditInputError(
                f"{location}.status is not a closed enum value: {status!r}"
            )
        boundary_changed = value["contract_boundary_changed"]
        if not isinstance(boundary_changed, bool):
            raise AuditInputError(
                f"{location}.contract_boundary_changed must be boolean"
            )
        allowed_namespaces = (
            fidelity_namespaces
            if _clause_family(clause_id) in fidelity_families
            else None
        )
        parsed_clauses.append(
            ClauseJudgment(
                clause_id=clause_id,
                status=status,
                evidence_ids=_evidence_ids(
                    value["evidence_ids"],
                    issued_evidence,
                    f"{location}.evidence_ids",
                    allowed_namespaces,
                ),
                reason=_non_empty_text(value["reason"], location),
                contract_boundary_changed=boundary_changed,
            )
        )

    paths = _require_object(
        response["path_assessments"], "code judgment.path_assessments"
    )
    if set(paths) != set(path_ids) or len(paths) != len(path_ids):
        raise AuditInputError(
            "code judgment must contain exactly the runtime-issued "
            "changed-path IDs"
        )
    parsed_paths = []
    for path_id in path_ids:
        location = f"code judgment.path_assessments.{path_id}"
        value = _require_exact_keys(
            paths[path_id],
            {"surface", "yagni_items", "reuse_items"},
            location,
        )
        surface = _require_exact_keys(
            value["surface"],
            {"status", "evidence_ids", "reason"},
            f"{location}.surface",
        )
        surface_status = surface["status"]
        if surface_status not in clause_statuses:
            raise AuditInputError(
                f"{location}.surface.status is not a closed enum value: "
                f"{surface_status!r}"
            )
        if not isinstance(value["yagni_items"], list):
            raise AuditInputError(f"{location}.yagni_items must be a list")
        if not isinstance(value["reuse_items"], list):
            raise AuditInputError(f"{location}.reuse_items must be a list")
        parsed_paths.append(
            PathAssessment(
                path_id=path_id,
                surface=SurfaceJudgment(
                    status=surface_status,
                    evidence_ids=_evidence_ids(
                        surface["evidence_ids"],
                        issued_evidence,
                        f"{location}.surface.evidence_ids",
                    ),
                    reason=_non_empty_text(
                        surface["reason"], f"{location}.surface"
                    ),
                ),
                yagni_items=tuple(
                    _parse_axis_item(
                        item,
                        issued_evidence,
                        f"{location}.yagni_items[{index}]",
                        _YAGNI_KINDS,
                    )
                    for index, item in enumerate(value["yagni_items"])
                ),
                reuse_items=tuple(
                    _parse_axis_item(
                        item,
                        issued_evidence,
                        f"{location}.reuse_items[{index}]",
                        _REUSE_KINDS,
                    )
                    for index, item in enumerate(value["reuse_items"])
                ),
            )
        )

    if not isinstance(response["deviations"], list):
        raise AuditInputError("code judgment.deviations must be a list")
    parsed_deviations = []
    for index, raw in enumerate(response["deviations"]):
        location = f"code judgment.deviations[{index}]"
        value = _require_exact_keys(
            raw,
            {
                "path_id",
                "line",
                "description",
                "evidence_ids",
                "reason",
            },
            location,
        )
        if value["path_id"] not in path_ids:
            raise AuditInputError(
                f"{location}.path_id is not a runtime-issued changed-path ID"
            )
        line = value["line"]
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise AuditInputError(f"{location}.line must be a positive integer")
        parsed_deviations.append(
            (
                value["path_id"],
                line,
                _non_empty_text(
                    value["description"], location, "non-empty description"
                ),
                _evidence_ids(
                    value["evidence_ids"],
                    issued_evidence,
                    f"{location}.evidence_ids",
                ),
                _non_empty_text(value["reason"], location),
            )
        )
    parsed_deviations.sort(key=lambda item: (item[0], item[1], item[2]))
    deviations = tuple(
        Deviation(
            deviation_id=f"U{index}",
            path_id=value[0],
            line=value[1],
            description=value[2],
            evidence_ids=value[3],
            reason=value[4],
        )
        for index, value in enumerate(parsed_deviations, 1)
    )
    return CodeJudgment(
        clauses=tuple(parsed_clauses),
        path_assessments=tuple(parsed_paths),
        deviations=deviations,
    )


def _aggregate_fidelity(clauses, rules):
    owned = [
        clause
        for clause in clauses
        if _clause_family(clause.clause_id) in rules.fidelity_families
    ]
    if any(
        clause.status == "UNMET"
        or (
            clause.status == "EXCEEDED"
            and clause.contract_boundary_changed
        )
        for clause in owned
    ):
        return "FAIL"
    if any(clause.status == "INDETERMINATE" for clause in owned):
        return "PARTIAL"
    return "PASS"


def _aggregate_yagni(path_assessments):
    kinds = [
        item.kind
        for assessment in path_assessments
        for item in assessment.yagni_items
    ]
    if any(kind in _STRUCTURAL_YAGNI_KINDS for kind in kinds):
        return "FAIL"
    if kinds.count("UNEARNED_LOCAL") >= 2:
        return "FAIL"
    if (
        "UNEARNED_LOCAL" in kinds
        or any(kind.startswith("QUESTIONABLE_") for kind in kinds)
    ):
        return "WARNING"
    return "PASS"


def _aggregate_reuse(path_assessments):
    item_groups = [
        assessment.reuse_items for assessment in path_assessments
    ]
    kinds = [item.kind for items in item_groups for item in items]
    if any(kind in {"DUPLICATED", "BYPASSED"} for kind in kinds):
        return "FAIL"
    if (
        any(not items for items in item_groups)
        or any(kind in {"NEAR_DUPLICATE", "INDETERMINATE"} for kind in kinds)
    ):
        return "WARNING"
    return "PASS"


def _aggregate_documented(ledger_entries):
    if not ledger_entries:
        return "NONE"
    if all(entry.status == "VERIFIED" for entry in ledger_entries):
        return "ACCEPTED"
    return "QUESTIONABLE"


def _aggregate_undocumented(deviations, deviation_matches, ledger_entries):
    verified = {
        entry.ledger_id
        for entry in ledger_entries
        if entry.status == "VERIFIED"
    }
    documented = {
        match.deviation_id
        for match in deviation_matches
        if match.ledger_id in verified
    }
    return (
        "PRESENT"
        if any(item.deviation_id not in documented for item in deviations)
        else "NONE"
    )


def _validate_reconciliation(code, reconciliation, rules):
    if not isinstance(reconciliation, ReconciliationJudgment):
        raise AuditInputError(
            "reconciliation must be a ReconciliationJudgment"
        )
    if not isinstance(reconciliation.contract_obsolete, bool):
        raise AuditInputError("contract_obsolete must be boolean")
    if not isinstance(reconciliation.acceptance_qa_exists, bool):
        raise AuditInputError("acceptance_qa_exists must be boolean")
    ledger_ids = [entry.ledger_id for entry in reconciliation.ledger_entries]
    if (
        any(not isinstance(item, str) or not item for item in ledger_ids)
        or len(ledger_ids) != len(set(ledger_ids))
    ):
        raise AuditInputError("ledger IDs must be unique non-empty strings")
    allowed_statuses = set(rules.statuses["ledger"])
    if any(
        entry.status not in allowed_statuses
        for entry in reconciliation.ledger_entries
    ):
        raise AuditInputError("ledger status is not a closed enum value")
    deviation_ids = {item.deviation_id for item in code.deviations}
    seen_matches = set()
    for match in reconciliation.deviation_matches:
        if match.deviation_id not in deviation_ids:
            raise AuditInputError("deviation match cites an unknown deviation")
        if match.ledger_id not in ledger_ids:
            raise AuditInputError("deviation match cites an unknown ledger ID")
        if match.deviation_id in seen_matches:
            raise AuditInputError("deviation match duplicates a deviation ID")
        seen_matches.add(match.deviation_id)


def _condition_key(
    fidelity,
    yagni,
    reuse,
    documented,
    undocumented,
    contract_obsolete,
    rules,
):
    simplicity = yagni != "PASS" or reuse != "PASS"
    unresolved = (
        fidelity == "PARTIAL"
        or documented == "QUESTIONABLE"
        or undocumented == "PRESENT"
    )
    conditions = {
        "CONTRACT_OBSOLETE": contract_obsolete,
        "FIDELITY_FAIL_WITH_SIMPLICITY": (
            fidelity == "FAIL" and simplicity
        ),
        "FIDELITY_FAIL": fidelity == "FAIL",
        "UNRESOLVED_WITH_SIMPLICITY": unresolved and simplicity,
        "UNRESOLVED": unresolved,
        "SIMPLICITY_ONLY": fidelity == "PASS" and simplicity,
        "PASS_WITH_DOCUMENTED_DRIFT": (
            fidelity == "PASS"
            and not simplicity
            and documented == "ACCEPTED"
            and undocumented == "NONE"
        ),
        "PASS": (
            fidelity == "PASS"
            and not simplicity
            and documented == "NONE"
            and undocumented == "NONE"
        ),
    }
    for name in rules.precedence:
        if conditions[name]:
            return name
    raise AuditInputError("axis combination has no precedence rule")


def _verdict(condition):
    if condition in {
        "CONTRACT_OBSOLETE",
        "FIDELITY_FAIL_WITH_SIMPLICITY",
        "FIDELITY_FAIL",
    }:
        return "CONTRACT VIOLATED"
    if condition in {
        "UNRESOLVED_WITH_SIMPLICITY",
        "UNRESOLVED",
        "SIMPLICITY_ONLY",
    }:
        return "NEEDS HUMAN REVIEW"
    if condition == "PASS_WITH_DOCUMENTED_DRIFT":
        return "PASS WITH DOCUMENTED DRIFT"
    return "PASS"


def _route(condition, acceptance_qa_exists, rules):
    route = rules.routes[condition]
    if isinstance(route, Mapping):
        key = "acceptance_qa_exists" if acceptance_qa_exists else "otherwise"
        return route[key]
    return route


def _finding_count(
    code,
    reconciliation,
    fidelity,
    yagni,
    reuse,
    documented,
    undocumented,
    contract_obsolete,
):
    count = int(contract_obsolete)
    if fidelity != "PASS":
        count += sum(
            clause.status in {"UNMET", "INDETERMINATE"}
            or (
                clause.status == "EXCEEDED"
                and clause.contract_boundary_changed
            )
            for clause in code.clauses
            if _clause_family(clause.clause_id)
            in {"O", "B", "N", "I", "C", "A"}
        )
    if yagni != "PASS":
        count += sum(
            item.kind.startswith(("UNEARNED_", "QUESTIONABLE_"))
            for path in code.path_assessments
            for item in path.yagni_items
        )
    if reuse != "PASS":
        count += sum(
            item.kind
            in {
                "DUPLICATED",
                "BYPASSED",
                "NEAR_DUPLICATE",
                "INDETERMINATE",
            }
            for path in code.path_assessments
            for item in path.reuse_items
        )
        count += sum(not path.reuse_items for path in code.path_assessments)
    if documented == "QUESTIONABLE":
        count += sum(
            entry.status != "VERIFIED"
            for entry in reconciliation.ledger_entries
        )
    if undocumented == "PRESENT":
        verified = {
            entry.ledger_id
            for entry in reconciliation.ledger_entries
            if entry.status == "VERIFIED"
        }
        documented_ids = {
            match.deviation_id
            for match in reconciliation.deviation_matches
            if match.ledger_id in verified
        }
        count += sum(
            item.deviation_id not in documented_ids
            for item in code.deviations
        )
    return count


def aggregate(code, reconciliation, rules) -> AuditDecision:
    """Aggregate validated semantic judgments using only executable policy."""
    if not isinstance(code, CodeJudgment):
        raise AuditInputError("code must be a validated CodeJudgment")
    if not isinstance(rules, RulePack):
        raise AuditInputError("rules must be a validated RulePack")
    _validate_reconciliation(code, reconciliation, rules)
    fidelity = _aggregate_fidelity(code.clauses, rules)
    yagni = _aggregate_yagni(code.path_assessments)
    reuse = _aggregate_reuse(code.path_assessments)
    documented = _aggregate_documented(reconciliation.ledger_entries)
    undocumented = _aggregate_undocumented(
        code.deviations,
        reconciliation.deviation_matches,
        reconciliation.ledger_entries,
    )
    condition = _condition_key(
        fidelity,
        yagni,
        reuse,
        documented,
        undocumented,
        reconciliation.contract_obsolete,
        rules,
    )
    count = _finding_count(
        code,
        reconciliation,
        fidelity,
        yagni,
        reuse,
        documented,
        undocumented,
        reconciliation.contract_obsolete,
    )
    return AuditDecision(
        fidelity=fidelity,
        yagni=yagni,
        reuse=reuse,
        documented_drift=documented,
        undocumented_drift=undocumented,
        verdict=_verdict(condition),
        route=tuple(
            _route(condition, reconciliation.acceptance_qa_exists, rules)
        ),
        finding_ids=tuple(f"F{index}" for index in range(1, count + 1)),
    )
