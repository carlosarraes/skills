"""Pure aggregate, precedence, routing, and stable-finding policy."""

import re
from collections.abc import Mapping

from audit_domain import (
    AuditDecision,
    AuditInputError,
    CodeJudgment,
    Finding,
    ReconciliationJudgment,
    RulePack,
    clause_family,
)


STRUCTURAL_YAGNI = {
    "UNEARNED_MODULE",
    "UNEARNED_RUNTIME_DEPENDENCY",
    "UNEARNED_CONFIGURATION",
    "UNEARNED_PUBLIC_INTERFACE",
}
REUSE_FAILURE = {"DUPLICATED", "BYPASSED"}
REUSE_WARNING = {"NEAR_DUPLICATE", "INDETERMINATE"}


def _aggregate_fidelity(clauses, rules):
    owned = [
        clause
        for clause in clauses
        if clause_family(clause.clause_id) in rules.fidelity_families
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


def _aggregate_yagni(paths):
    kinds = [
        item.kind for path in paths for item in path.yagni_items
    ]
    if any(kind in STRUCTURAL_YAGNI for kind in kinds):
        return "FAIL"
    if kinds.count("UNEARNED_LOCAL") >= 2:
        return "FAIL"
    if (
        "UNEARNED_LOCAL" in kinds
        or any(kind.startswith("QUESTIONABLE_") for kind in kinds)
    ):
        return "WARNING"
    return "PASS"


def _aggregate_reuse(paths):
    groups = [path.reuse_items for path in paths]
    kinds = [item.kind for group in groups for item in group]
    if any(kind in REUSE_FAILURE for kind in kinds):
        return "FAIL"
    if any(not group for group in groups) or any(
        kind in REUSE_WARNING for kind in kinds
    ):
        return "WARNING"
    return "PASS"


def _aggregate_documented(entries):
    if not entries:
        return "NONE"
    if all(entry.status == "VERIFIED" for entry in entries):
        return "ACCEPTED"
    return "QUESTIONABLE"


def _verified_matches(reconciliation):
    verified = {
        entry.ledger_id
        for entry in reconciliation.ledger_entries
        if entry.status == "VERIFIED"
    }
    return {
        match.deviation_id
        for match in reconciliation.deviation_matches
        if match.ledger_id in verified
    }


def _aggregate_undocumented(deviations, reconciliation):
    matched = _verified_matches(reconciliation)
    return (
        "PRESENT"
        if any(item.deviation_id not in matched for item in deviations)
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
    if any(
        entry.status not in rules.statuses["ledger"]
        for entry in reconciliation.ledger_entries
    ):
        raise AuditInputError("ledger status is not a closed enum value")
    deviation_ids = {item.deviation_id for item in code.deviations}
    matched = set()
    for match in reconciliation.deviation_matches:
        if match.deviation_id not in deviation_ids:
            raise AuditInputError("deviation match cites an unknown deviation")
        if match.ledger_id not in ledger_ids:
            raise AuditInputError("deviation match cites an unknown ledger ID")
        if match.deviation_id in matched:
            raise AuditInputError("deviation match duplicates a deviation ID")
        matched.add(match.deviation_id)


def _condition(
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
    matches = {
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
        if matches[name]:
            return name
    raise AuditInputError("axis combination has no precedence rule")


def _verdict(condition):
    if condition.startswith("FIDELITY_") or condition == "CONTRACT_OBSOLETE":
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


def _route(condition, reconciliation, rules):
    route = rules.routes[condition]
    if isinstance(route, Mapping):
        key = (
            "acceptance_qa_exists"
            if reconciliation.acceptance_qa_exists
            else "otherwise"
        )
        return route[key]
    return route


def _finding_candidates(
    code,
    reconciliation,
    fidelity,
    yagni,
    reuse,
    documented,
    undocumented,
):
    candidates = []
    if reconciliation.contract_obsolete:
        candidates.append(
            ("authority", "CONTRACT", "", 0, "Contract is obsolete.")
        )
    if fidelity != "PASS":
        for clause in code.clauses:
            if clause_family(clause.clause_id) not in {
                "O",
                "B",
                "N",
                "I",
                "C",
                "A",
            }:
                continue
            if clause.status in {"UNMET", "INDETERMINATE"} or (
                clause.status == "EXCEEDED"
                and clause.contract_boundary_changed
            ):
                candidates.append(
                    (
                        "clause",
                        clause.clause_id,
                        "",
                        0,
                        clause.reason,
                    )
                )
    if yagni != "PASS":
        for path in code.path_assessments:
            for item in path.yagni_items:
                if item.kind.startswith(("UNEARNED_", "QUESTIONABLE_")):
                    candidates.append(
                        (
                            "yagni",
                            item.item_id,
                            path.path_id,
                            0,
                            item.reason,
                        )
                    )
    if reuse != "PASS":
        for path in code.path_assessments:
            if not path.reuse_items:
                candidates.append(
                    (
                        "reuse",
                        f"{path.path_id}:R0",
                        path.path_id,
                        0,
                        "Reuse evidence is missing.",
                    )
                )
            for item in path.reuse_items:
                if item.kind in REUSE_FAILURE | REUSE_WARNING:
                    candidates.append(
                        (
                            "reuse",
                            item.item_id,
                            path.path_id,
                            0,
                            item.reason,
                        )
                    )
    if documented == "QUESTIONABLE":
        for entry in reconciliation.ledger_entries:
            if entry.status != "VERIFIED":
                candidates.append(
                    (
                        "ledger",
                        entry.ledger_id,
                        "",
                        0,
                        f"Ledger status is {entry.status}.",
                    )
                )
    if undocumented == "PRESENT":
        matched = _verified_matches(reconciliation)
        for deviation in code.deviations:
            if deviation.deviation_id not in matched:
                candidates.append(
                    (
                        "deviation",
                        deviation.deviation_id,
                        deviation.path_id,
                        deviation.line,
                        deviation.reason,
                    )
                )
    return candidates


def _natural_id(value):
    return re.sub(
        r"\d+",
        lambda match: f"{int(match.group()):020d}",
        value,
    )


def _findings(condition, candidates, rules):
    rank = rules.precedence.index(condition)
    ordered = sorted(
        candidates,
        key=lambda item: (
            rank,
            _natural_id(item[1]),
            item[2],
            item[3],
            item[0],
        ),
    )
    return tuple(
        Finding(
            finding_id=f"F{index}",
            condition=condition,
            source_kind=item[0],
            source_id=item[1],
            path_id=item[2],
            line=item[3],
            reason=item[4],
            sort_key=(
                rank,
                _natural_id(item[1]),
                item[2],
                item[3],
                item[0],
            ),
        )
        for index, item in enumerate(ordered, 1)
    )


def aggregate(code, reconciliation, rules) -> AuditDecision:
    """Apply pure v1 aggregates, precedence, routes, and stable findings."""
    if not isinstance(code, CodeJudgment):
        raise AuditInputError("code must be a validated CodeJudgment")
    if not isinstance(rules, RulePack):
        raise AuditInputError("rules must be a validated RulePack")
    _validate_reconciliation(code, reconciliation, rules)
    fidelity = _aggregate_fidelity(code.clauses, rules)
    yagni = _aggregate_yagni(code.path_assessments)
    reuse = _aggregate_reuse(code.path_assessments)
    documented = _aggregate_documented(reconciliation.ledger_entries)
    undocumented = _aggregate_undocumented(code.deviations, reconciliation)
    condition = _condition(
        fidelity,
        yagni,
        reuse,
        documented,
        undocumented,
        reconciliation.contract_obsolete,
        rules,
    )
    candidates = _finding_candidates(
        code,
        reconciliation,
        fidelity,
        yagni,
        reuse,
        documented,
        undocumented,
    )
    return AuditDecision(
        fidelity=fidelity,
        yagni=yagni,
        reuse=reuse,
        documented_drift=documented,
        undocumented_drift=undocumented,
        verdict=_verdict(condition),
        route=tuple(_route(condition, reconciliation, rules)),
        findings=_findings(condition, candidates, rules),
    )
