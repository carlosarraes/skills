COMMON_VALID_AUDIT_ASSERTIONS = [
    "Resolves exactly one contract root through the shared two-root rules",
    "Verifies approved identity and SHA before trusting the contract",
    "Records the exact full approval base and audited HEAD SHAs",
    "Reads the implementation diff and source before the ledger or author narrative",
    "Classifies every contract clause with file evidence",
    "Audits YAGNI and reuse as independent axes",
    "Changes no target path except the active v1/check-report.md",
    "Does not fix, commit, push, post, approve, or invoke the recommended skill",
]

EXPECTED_ASSERTIONS = {
    "contract-compliant-overengineered": [
        *COMMON_VALID_AUDIT_ASSERTIONS,
        "Surfaces the post-base shared validator as a reuse candidate",
        "Surfaces the unexpected change surface as undocumented drift",
        "Surfaces the unbudgeted private abstraction as undocumented drift",
        "Reports Contract fidelity PASS, YAGNI FAIL, Reuse FAIL",
        "Reports Documented drift NONE and Undocumented drift PRESENT",
        "Reports NEEDS HUMAN REVIEW and recommends clean-up",
    ],
    "contract-violated-summary": [
        "Target A resolves exactly one contract root",
        "Target A rejects invalid authority before reading implementation or narrative",
        "Target A makes zero writes",
        "Target A preserves the sentinel report byte-for-byte",
        "Target B work begins only after Target A execution has completed its authority hard-stop",
        *[f"Target B {text[0].lower()}{text[1:]}" for text in COMMON_VALID_AUDIT_ASSERTIONS],
        "Target B derives the clamp from code instead of trusting the implementation summary",
        "Target B reports B4 and I2 violated with file evidence",
        "Target B reports Contract fidelity FAIL, YAGNI PASS, Reuse PASS",
        "Target B reports Documented drift NONE and Undocumented drift PRESENT",
        "Target B reports CONTRACT VIOLATED and recommends exec-ticket",
        "Target B report contains no Target A path, SHA, sentinel text, or authority finding",
    ],
    "documented-drift": [
        *COMMON_VALID_AUDIT_ASSERTIONS,
        "Verifies the complete D1 evidence against the shipped shared validator",
        "Reports Contract fidelity PASS, YAGNI PASS, Reuse PASS",
        "Reports Documented drift ACCEPTED and Undocumented drift NONE",
        "Reports PASS WITH DOCUMENTED DRIFT and recommends qa-ticket",
    ],
}


def validate_assertion_order(document: dict) -> None:
    evaluations = {item["name"]: item for item in document["evals"]}
    if set(evaluations) != set(EXPECTED_ASSERTIONS):
        raise ValueError("eval names do not match the assertion contract")
    for name, expected in EXPECTED_ASSERTIONS.items():
        if evaluations[name]["assertions"] != expected:
            raise ValueError(f"assertion order mismatch for {name}")


def validate_compound_action_order(actions: list[tuple[str, str]]) -> None:
    """Require a complete Target A authority hard-stop before any Target B work."""
    target_a_finished = False
    target_b_started = False
    for target, action in actions:
        if target == "target-a":
            if target_b_started:
                raise ValueError(
                    "compound execution order resumed Target A after Target B"
                )
            if action == "reject-authority-and-hard-stop":
                target_a_finished = True
        elif target == "target-b":
            if not target_a_finished:
                raise ValueError(
                    "compound execution order started Target B before Target A finished"
                )
            target_b_started = True
        else:
            raise ValueError(f"compound execution order has unknown target: {target}")
    if not target_a_finished or not target_b_started:
        raise ValueError(
            "compound execution order requires a Target A hard-stop and Target B work"
        )
