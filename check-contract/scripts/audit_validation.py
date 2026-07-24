"""Closed parsing and validation for code-judgment responses."""

from pathlib import Path

from audit_domain import (
    AuditInputError,
    AxisItem,
    ClauseJudgment,
    CodeJudgment,
    Deviation,
    PathAssessment,
    SurfaceJudgment,
    RulePack,
    clause_family,
    load_rules,
    require_exact_keys,
    require_object,
)


YAGNI_KINDS = frozenset(
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
REUSE_KINDS = frozenset(
    {
        "REUSED",
        "NO_REUSE_AVAILABLE",
        "DUPLICATED",
        "BYPASSED",
        "NEAR_DUPLICATE",
        "INDETERMINATE",
    }
)
DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "change-contract"
    / "references"
    / "contract-check-rules.json"
)


def allowed_clause_evidence_ids(
    clause_id: str,
    issued_evidence_ids: tuple[str, ...] | list[str],
    rules: RulePack,
) -> tuple[str, ...]:
    issued = tuple(issued_evidence_ids)
    if clause_family(clause_id) not in rules.fidelity_families:
        return issued
    namespaces = set(rules.fidelity_evidence_namespaces)
    return tuple(
        evidence_id
        for evidence_id in issued
        if evidence_id.partition(":")[0] in namespaces
    )


def _runtime_ids(packet, key, label):
    packet = require_object(packet, "packet")
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


def _text(value, location, label="non-empty reason"):
    if not isinstance(value, str) or not value.strip():
        raise AuditInputError(f"{location} requires {label} text")
    return value.strip()


def _evidence(value, issued, location, namespaces=None):
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise AuditInputError(
            f"{location} issued evidence IDs must be unique strings"
        )
    unknown = sorted(set(value) - issued)
    if unknown:
        raise AuditInputError(
            f"{location} cites evidence outside the issued evidence IDs: "
            f"{unknown}"
        )
    if namespaces is not None:
        invalid = [
            item for item in value if item.partition(":")[0] not in namespaces
        ]
        if invalid:
            raise AuditInputError(
                f"{location} violates fidelity evidence namespace ownership: "
                f"{sorted(invalid)}"
            )
    return tuple(value)


def _parse_clause(clause_id, value, issued, rules):
    location = f"code judgment.clauses.{clause_id}"
    value = require_exact_keys(
        value,
        {
            "status",
            "evidence_ids",
            "reason",
            "contract_boundary_changed",
        },
        location,
    )
    status = value["status"]
    if status not in rules.statuses["clause"]:
        raise AuditInputError(
            f"{location}.status is not a closed enum value: {status!r}"
        )
    boundary = value["contract_boundary_changed"]
    if not isinstance(boundary, bool):
        raise AuditInputError(
            f"{location}.contract_boundary_changed must be boolean"
        )
    allowed = allowed_clause_evidence_ids(clause_id, issued, rules)
    evidence_ids = _evidence(
        value["evidence_ids"],
        issued,
        f"{location}.evidence_ids",
    )
    invalid = sorted(set(evidence_ids) - set(allowed))
    if invalid:
        raise AuditInputError(
            f"{location}.evidence_ids violates fidelity evidence namespace ownership: "
            f"{invalid}"
        )
    return ClauseJudgment(
        clause_id=clause_id,
        status=status,
        evidence_ids=evidence_ids,
        reason=_text(value["reason"], location),
        contract_boundary_changed=boundary,
    )


def _parse_items(path_id, values, axis, issued, allowed_kinds):
    location = f"code judgment.path_assessments.{path_id}.{axis}_items"
    if not isinstance(values, list):
        raise AuditInputError(f"{location} must be a list")
    parsed = []
    for index, raw in enumerate(values):
        item_location = f"{location}[{index}]"
        value = require_exact_keys(
            raw, {"kind", "evidence_ids", "reason"}, item_location
        )
        if value["kind"] not in allowed_kinds:
            raise AuditInputError(
                f"{item_location}.kind is not a closed enum value: "
                f"{value['kind']!r}"
            )
        parsed.append(
            (
                value["kind"],
                _evidence(
                    value["evidence_ids"],
                    issued,
                    f"{item_location}.evidence_ids",
                ),
                _text(value["reason"], item_location),
            )
        )
    parsed.sort()
    prefix = "Y" if axis == "yagni" else "R"
    return tuple(
        AxisItem(
            item_id=f"{path_id}:{prefix}{index}",
            kind=item[0],
            evidence_ids=item[1],
            reason=item[2],
        )
        for index, item in enumerate(parsed, 1)
    )


def _parse_path(path_id, value, issued, rules):
    location = f"code judgment.path_assessments.{path_id}"
    value = require_exact_keys(
        value, {"surface", "yagni_items", "reuse_items"}, location
    )
    surface = require_exact_keys(
        value["surface"],
        {"status", "evidence_ids", "reason"},
        f"{location}.surface",
    )
    status = surface["status"]
    if status not in rules.statuses["clause"]:
        raise AuditInputError(
            f"{location}.surface.status is not a closed enum value: "
            f"{status!r}"
        )
    return PathAssessment(
        path_id=path_id,
        surface=SurfaceJudgment(
            status=status,
            evidence_ids=_evidence(
                surface["evidence_ids"],
                issued,
                f"{location}.surface.evidence_ids",
            ),
            reason=_text(surface["reason"], f"{location}.surface"),
        ),
        yagni_items=_parse_items(
            path_id,
            value["yagni_items"],
            "yagni",
            issued,
            YAGNI_KINDS,
        ),
        reuse_items=_parse_items(
            path_id,
            value["reuse_items"],
            "reuse",
            issued,
            REUSE_KINDS,
        ),
    )


def _explicit_deviations(values, path_ids, issued):
    if not isinstance(values, list):
        raise AuditInputError("code judgment.deviations must be a list")
    parsed = []
    for index, raw in enumerate(values):
        location = f"code judgment.deviations[{index}]"
        value = require_exact_keys(
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
        path_id = value["path_id"]
        if path_id not in path_ids:
            raise AuditInputError(
                f"{location}.path_id is not a runtime-issued changed-path ID"
            )
        line = value["line"]
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise AuditInputError(f"{location}.line must be a positive integer")
        description = _text(
            value["description"], location, "non-empty description"
        )
        parsed.append(
            (
                "explicit",
                f"{path_id}:{line}:{description}",
                path_id,
                line,
                description,
                _evidence(
                    value["evidence_ids"],
                    issued,
                    f"{location}.evidence_ids",
                ),
                _text(value["reason"], location),
            )
        )
    return parsed


def _derived_deviations(clauses, paths):
    derived = []
    for clause in clauses:
        if clause_family(clause.clause_id) in {"S", "K"} and (
            clause.status != "MET"
        ):
            derived.append(
                (
                    "clause",
                    clause.clause_id,
                    "",
                    0,
                    f"{clause.clause_id}: {clause.reason}",
                    clause.evidence_ids,
                    clause.reason,
                )
            )
    for path in paths:
        if path.surface.status != "MET":
            derived.append(
                (
                    "surface",
                    path.path_id,
                    path.path_id,
                    0,
                    f"{path.path_id}: {path.surface.reason}",
                    path.surface.evidence_ids,
                    path.surface.reason,
                )
            )
    return derived


def _assign_deviation_ids(values):
    values.sort(key=lambda item: (item[2], item[3], item[4], item[0], item[1]))
    return tuple(
        Deviation(
            deviation_id=f"U{index}",
            source_kind=item[0],
            source_id=item[1],
            path_id=item[2],
            line=item[3],
            description=item[4],
            evidence_ids=item[5],
            reason=item[6],
        )
        for index, item in enumerate(values, 1)
    )


def validate_code_judgment(packet, response) -> CodeJudgment:
    """Validate a response and derive every required drift identity."""
    rules = load_rules(DEFAULT_RULES_PATH)
    clause_ids = _runtime_ids(packet, "clause_ids", "clause IDs")
    path_ids = _runtime_ids(packet, "changed_path_ids", "changed-path IDs")
    issued = set(_runtime_ids(packet, "evidence_ids", "issued evidence IDs"))
    response = require_exact_keys(
        response,
        {"clauses", "path_assessments", "deviations"},
        "code judgment",
    )
    clause_values = require_object(
        response["clauses"], "code judgment.clauses"
    )
    if set(clause_values) != set(clause_ids):
        raise AuditInputError(
            "code judgment must contain exactly the runtime-issued clause IDs"
        )
    path_values = require_object(
        response["path_assessments"], "code judgment.path_assessments"
    )
    if set(path_values) != set(path_ids):
        raise AuditInputError(
            "code judgment must contain exactly the runtime-issued "
            "changed-path IDs"
        )
    clauses = tuple(
        _parse_clause(clause_id, clause_values[clause_id], issued, rules)
        for clause_id in clause_ids
    )
    paths = tuple(
        _parse_path(path_id, path_values[path_id], issued, rules)
        for path_id in path_ids
    )
    deviations = _explicit_deviations(
        response["deviations"], set(path_ids), issued
    )
    deviations.extend(_derived_deviations(clauses, paths))
    return CodeJudgment(
        clauses=clauses,
        path_assessments=paths,
        deviations=_assign_deviation_ids(deviations),
    )
