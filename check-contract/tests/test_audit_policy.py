import dataclasses
import importlib
import importlib.util
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "check-contract" / "scripts" / "audit_runtime.py"
RULES = (
    ROOT
    / "change-contract"
    / "references"
    / "contract-check-rules.json"
)


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("audit_runtime", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


CASES = (
    {
        "name": "surface-and-private-class-do-not-fail-fidelity",
        "owned": {
            "O1": "MET",
            "B1": "MET",
            "I1": "MET",
            "C1": "MET",
            "A-B1": "MET",
        },
        "surface": "EXCEEDED",
        "yagni_items": ["UNEARNED_LOCAL"],
        "reuse_items": ["DUPLICATED"],
        "expected": (
            "PASS",
            "WARNING",
            "FAIL",
            "NEEDS HUMAN REVIEW",
            ["clean-up"],
        ),
    },
    {
        "name": "required-validation-is-not-bloat",
        "owned": {
            "O1": "MET",
            "B1": "UNMET",
            "I1": "MET",
            "C1": "MET",
            "A-B1": "INDETERMINATE",
        },
        "surface": "MET",
        "yagni_items": [],
        "reuse_items": ["REUSED"],
        "expected": (
            "FAIL",
            "PASS",
            "PASS",
            "CONTRACT VIOLATED",
            ["exec-ticket"],
        ),
    },
)


class AuditPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.rules = cls.module.load_rules(RULES)

    def setUp(self):
        self.packet = {
            "clause_ids": [
                "O1",
                "B1",
                "I1",
                "C1",
                "A-B1",
                "S1",
                "K-MODULES",
            ],
            "changed_path_ids": ["P1"],
            "evidence_ids": [
                "behavior:O1",
                "behavior:B1",
                "risk:I1",
                "public-contract:C1",
                "acceptance:A-B1",
                "surface:P1",
                "complexity:P1",
                "complexity:K-MODULES",
                "reuse:P1",
            ],
            "semantics": {
                "generation": "a" * 64,
                "issued_facts": {
                    "clause_statuses": {},
                    "helpers": [
                        {
                            "fact_id": "H1",
                            "use_status": "NOT_USED",
                            "used_by_path_ids": [],
                        }
                    ],
                },
            },
            "chronology": {"generation": "b" * 64},
        }

    def valid_code_response(
        self,
        *,
        owned=None,
        surface="MET",
        complexity="MET",
        yagni_items=(),
        reuse_items=("REUSED",),
        deviations=(),
    ):
        owned = owned or {
            "O1": "MET",
            "B1": "MET",
            "I1": "MET",
            "C1": "MET",
            "A-B1": "MET",
        }
        evidence = {
            "O1": "behavior:O1",
            "B1": "behavior:B1",
            "I1": "risk:I1",
            "C1": "public-contract:C1",
            "A-B1": "acceptance:A-B1",
        }
        clauses = {
            clause_id: {
                "status": status,
                "evidence_ids": [evidence[clause_id]],
                "reason": f"{clause_id} is judged from issued evidence.",
                "contract_boundary_changed": status == "EXCEEDED",
            }
            for clause_id, status in owned.items()
        }
        clauses["S1"] = {
            "status": surface,
            "evidence_ids": ["surface:P1"],
            "reason": "The expected change surface was inspected.",
            "contract_boundary_changed": False,
        }
        clauses["K-MODULES"] = {
            "status": complexity,
            "evidence_ids": ["complexity:K-MODULES"],
            "reason": "The module complexity budget was inspected.",
            "contract_boundary_changed": False,
        }
        return {
            "semantic_generation": self.packet["semantics"]["generation"],
            "chronology_generation": self.packet["chronology"]["generation"],
            "clauses": clauses,
            "path_assessments": {
                "P1": {
                    "surface": {
                        "status": surface,
                        "evidence_ids": ["surface:P1"],
                        "reason": "The path surface was classified.",
                    },
                    "yagni_items": [
                        {
                            "kind": kind,
                            "evidence_ids": ["complexity:P1"],
                            "reason": "The construct was classified.",
                        }
                        for kind in yagni_items
                    ],
                    "reuse_items": [
                        {
                            "kind": kind,
                            "helper_fact_ids": ["H1"],
                            "evidence_ids": ["reuse:P1"],
                            "reason": "The reuse search was classified.",
                        }
                        for kind in reuse_items
                    ],
                }
            },
            "deviations": list(deviations),
        }

    def reconcile(
        self,
        *,
        ledger_entries=(),
        deviation_matches=(),
        contract_obsolete=False,
        acceptance_qa_exists=False,
    ):
        return self.module.ReconciliationJudgment(
            ledger_entries=tuple(ledger_entries),
            deviation_matches=tuple(deviation_matches),
            contract_obsolete=contract_obsolete,
            acceptance_qa_exists=acceptance_qa_exists,
        )

    def test_observed_semantic_defects_have_independent_axes(self):
        for case in CASES:
            with self.subTest(case["name"]):
                response = self.valid_code_response(
                    owned=case["owned"],
                    surface=case["surface"],
                    yagni_items=case["yagni_items"],
                    reuse_items=case["reuse_items"],
                )
                code = self.module.validate_code_judgment(
                    self.packet, response
                )

                decision = self.module.aggregate(
                    code, self.reconcile(), self.rules
                )

                actual = (
                    decision.fidelity,
                    decision.yagni,
                    decision.reuse,
                    decision.verdict,
                    list(decision.route),
                )
                self.assertEqual(actual, case["expected"])

    def test_fidelity_rejects_simplicity_evidence_namespace(self):
        response = self.valid_code_response()
        response["clauses"]["O1"]["evidence_ids"] = ["complexity:P1"]

        with self.assertRaisesRegex(
            self.module.AuditInputError, "evidence namespace"
        ):
            self.module.validate_code_judgment(self.packet, response)

    def test_fidelity_namespace_policy_has_one_shared_derivation(self):
        validation = importlib.import_module("audit_validation")
        self.assertNotIn(
            "namespaces",
            inspect.signature(validation._evidence).parameters,
        )
        self.assertEqual(
            inspect.getsource(validation).count('partition(":")[0]'),
            1,
        )

    def test_validator_requires_exact_runtime_ids_and_closed_shapes(self):
        mutations = {}

        missing_clause = self.valid_code_response()
        missing_clause["clauses"].pop("B1")
        mutations["clause IDs"] = missing_clause

        extra_path = self.valid_code_response()
        extra_path["path_assessments"]["P2"] = dict(
            extra_path["path_assessments"]["P1"]
        )
        mutations["changed-path IDs"] = extra_path

        unknown_status = self.valid_code_response()
        unknown_status["clauses"]["B1"]["status"] = "MAYBE"
        mutations["closed enum"] = unknown_status

        unissued_evidence = self.valid_code_response()
        unissued_evidence["clauses"]["B1"]["evidence_ids"] = [
            "behavior:NOT-ISSUED"
        ]
        mutations["issued evidence"] = unissued_evidence

        empty_reason = self.valid_code_response()
        empty_reason["clauses"]["B1"]["reason"] = " \n"
        mutations["non-empty reason"] = empty_reason

        forbidden_field = self.valid_code_response()
        forbidden_field["verdict"] = "PASS"
        mutations["extra JSON keys"] = forbidden_field

        nested_extra = self.valid_code_response()
        nested_extra["clauses"]["B1"]["aggregate"] = "PASS"
        mutations["extra JSON keys"] = nested_extra

        for message, response in mutations.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    self.module.AuditInputError, message
                ):
                    self.module.validate_code_judgment(
                        self.packet, response
                    )

    def test_validator_rejects_unknown_judgment_item_kinds(self):
        for axis, kind in (
            ("yagni_items", "FUTURE_PROOFING"),
            ("reuse_items", "LOOKS_FINE"),
        ):
            response = self.valid_code_response()
            response["path_assessments"]["P1"][axis] = [
                {
                    "kind": kind,
                    **(
                        {"helper_fact_ids": ["H1"]}
                        if axis == "reuse_items"
                        else {}
                    ),
                    "evidence_ids": ["complexity:P1"],
                    "reason": "Unknown closed value.",
                }
            ]
            with self.subTest(axis=axis), self.assertRaisesRegex(
                self.module.AuditInputError, "closed enum"
            ):
                self.module.validate_code_judgment(self.packet, response)

    def test_fidelity_exceeded_uses_explicit_contract_boundary_judgment(self):
        owned = {
            "O1": "EXCEEDED",
            "B1": "MET",
            "I1": "MET",
            "C1": "MET",
            "A-B1": "MET",
        }
        response = self.valid_code_response(owned=owned)
        response["clauses"]["O1"]["contract_boundary_changed"] = False
        satisfied = self.module.validate_code_judgment(
            self.packet, response
        )
        violated_response = self.valid_code_response(owned=owned)
        violated = self.module.validate_code_judgment(
            self.packet, violated_response
        )

        self.assertEqual(
            self.module.aggregate(
                satisfied, self.reconcile(), self.rules
            ).fidelity,
            "PASS",
        )
        self.assertEqual(
            self.module.aggregate(
                violated, self.reconcile(), self.rules
            ).fidelity,
            "FAIL",
        )

    def test_drift_aggregation_matches_only_verified_ledger_entries(self):
        response = self.valid_code_response(
            deviations=[
                {
                    "path_id": "P1",
                    "line": 12,
                    "description": "Responsibility moved to another module.",
                    "evidence_ids": ["surface:P1"],
                    "reason": "The recorded surface differs.",
                }
            ]
        )
        code = self.module.validate_code_judgment(self.packet, response)
        ledger = self.module.LedgerEntry("D1", "VERIFIED")
        match = self.module.DeviationMatch("U1", "D1")

        undocumented = self.module.aggregate(
            code,
            self.reconcile(ledger_entries=(ledger,)),
            self.rules,
        )
        documented = self.module.aggregate(
            code,
            self.reconcile(
                ledger_entries=(ledger,),
                deviation_matches=(match,),
            ),
            self.rules,
        )

        self.assertEqual(undocumented.documented_drift, "ACCEPTED")
        self.assertEqual(undocumented.undocumented_drift, "PRESENT")
        self.assertEqual(undocumented.verdict, "NEEDS HUMAN REVIEW")
        self.assertEqual(documented.documented_drift, "ACCEPTED")
        self.assertEqual(documented.undocumented_drift, "NONE")
        self.assertEqual(
            (documented.verdict, documented.route),
            ("PASS WITH DOCUMENTED DRIFT", ("qa-ticket",)),
        )

    def test_pass_routes_to_qa_pr_only_when_acceptance_qa_exists(self):
        code = self.module.validate_code_judgment(
            self.packet, self.valid_code_response()
        )

        without_qa = self.module.aggregate(
            code, self.reconcile(), self.rules
        )
        with_qa = self.module.aggregate(
            code,
            self.reconcile(acceptance_qa_exists=True),
            self.rules,
        )

        self.assertEqual(without_qa.route, ("qa-ticket",))
        self.assertEqual(with_qa.route, ("qa-pr",))

    def test_non_met_surface_and_complexity_are_derived_deviations(self):
        for axis, response in (
            (
                "surface",
                self.valid_code_response(surface="EXCEEDED"),
            ),
            (
                "complexity",
                self.valid_code_response(complexity="EXCEEDED"),
            ),
        ):
            with self.subTest(axis=axis):
                code = self.module.validate_code_judgment(
                    self.packet, response
                )
                decision = self.module.aggregate(
                    code, self.reconcile(), self.rules
                )

                self.assertTrue(code.deviations)
                self.assertEqual(decision.fidelity, "PASS")
                self.assertEqual(decision.yagni, "PASS")
                self.assertEqual(decision.reuse, "PASS")
                self.assertEqual(decision.undocumented_drift, "PRESENT")
                self.assertEqual(decision.verdict, "NEEDS HUMAN REVIEW")
                self.assertEqual(decision.route, ("qa-ticket",))

    def test_deviation_and_finding_identity_is_permutation_stable(self):
        deviations = [
            {
                "path_id": "P1",
                "line": 20,
                "description": "Second deviation.",
                "evidence_ids": ["surface:P1"],
                "reason": "Second fact.",
            },
            {
                "path_id": "P1",
                "line": 10,
                "description": "First deviation.",
                "evidence_ids": ["surface:P1"],
                "reason": "First fact.",
            },
        ]
        responses = (
            self.valid_code_response(deviations=deviations),
            self.valid_code_response(deviations=reversed(deviations)),
        )
        results = []
        for response in responses:
            code = self.module.validate_code_judgment(
                self.packet, response
            )
            decision = self.module.aggregate(
                code, self.reconcile(), self.rules
            )
            results.append(
                (
                    tuple(
                        (
                            item.deviation_id,
                            item.path_id,
                            item.line,
                            item.description,
                        )
                        for item in code.deviations
                    ),
                    decision.findings,
                )
            )

        self.assertEqual(results[0], results[1])
        self.assertEqual(
            results[0][0],
            (
                ("U1", "P1", 10, "First deviation."),
                ("U2", "P1", 20, "Second deviation."),
            ),
        )
        findings = results[0][1]
        self.assertEqual(
            [
                (
                    item.finding_id,
                    item.source_kind,
                    item.source_id,
                    item.path_id,
                    item.line,
                )
                for item in findings
            ],
            [
                ("F1", "deviation", "U1", "P1", 10),
                ("F2", "deviation", "U2", "P1", 20),
            ],
        )
        self.assertEqual(
            tuple(item.sort_key for item in findings),
            tuple(sorted(item.sort_key for item in findings)),
        )
        self.assertEqual(
            tuple(item.finding_id for item in findings),
            self.module.aggregate(
                self.module.validate_code_judgment(
                    self.packet, responses[0]
                ),
                self.reconcile(),
                self.rules,
            ).finding_ids,
        )

    def test_precedence_is_exhaustive(self):
        cases = (
            (
                "obsolete",
                self.valid_code_response(),
                self.reconcile(contract_obsolete=True),
                ("CONTRACT VIOLATED", ("change-contract",)),
            ),
            (
                "fidelity-with-simplicity",
                self.valid_code_response(
                    owned={
                        "O1": "UNMET",
                        "B1": "MET",
                        "I1": "MET",
                        "C1": "MET",
                        "A-B1": "MET",
                    },
                    yagni_items=("UNEARNED_LOCAL",),
                ),
                self.reconcile(),
                ("CONTRACT VIOLATED", ("exec-ticket", "clean-up")),
            ),
            (
                "fidelity",
                self.valid_code_response(
                    owned={
                        "O1": "UNMET",
                        "B1": "MET",
                        "I1": "MET",
                        "C1": "MET",
                        "A-B1": "MET",
                    }
                ),
                self.reconcile(),
                ("CONTRACT VIOLATED", ("exec-ticket",)),
            ),
            (
                "unresolved-with-simplicity",
                self.valid_code_response(
                    owned={
                        "O1": "INDETERMINATE",
                        "B1": "MET",
                        "I1": "MET",
                        "C1": "MET",
                        "A-B1": "MET",
                    },
                    reuse_items=("NEAR_DUPLICATE",),
                ),
                self.reconcile(),
                ("NEEDS HUMAN REVIEW", ("clean-up",)),
            ),
            (
                "unresolved",
                self.valid_code_response(
                    owned={
                        "O1": "INDETERMINATE",
                        "B1": "MET",
                        "I1": "MET",
                        "C1": "MET",
                        "A-B1": "MET",
                    }
                ),
                self.reconcile(),
                ("NEEDS HUMAN REVIEW", ("qa-ticket",)),
            ),
            (
                "simplicity",
                self.valid_code_response(
                    yagni_items=("UNEARNED_LOCAL",)
                ),
                self.reconcile(),
                ("NEEDS HUMAN REVIEW", ("clean-up",)),
            ),
            (
                "documented-drift",
                self.valid_code_response(),
                self.reconcile(
                    ledger_entries=(
                        self.module.LedgerEntry("D1", "VERIFIED"),
                    )
                ),
                ("PASS WITH DOCUMENTED DRIFT", ("qa-ticket",)),
            ),
            (
                "pass",
                self.valid_code_response(),
                self.reconcile(),
                ("PASS", ("qa-ticket",)),
            ),
        )
        for name, response, reconciliation, expected in cases:
            with self.subTest(name=name):
                code = self.module.validate_code_judgment(
                    self.packet, response
                )
                decision = self.module.aggregate(
                    code, reconciliation, self.rules
                )
                self.assertEqual(
                    (decision.verdict, decision.route), expected
                )

    def test_yagni_and_reuse_thresholds(self):
        cases = (
            ("no-yagni", (), ("REUSED",), ("PASS", "PASS")),
            (
                "one-local",
                ("UNEARNED_LOCAL",),
                ("REUSED",),
                ("WARNING", "PASS"),
            ),
            (
                "two-local",
                ("UNEARNED_LOCAL", "UNEARNED_LOCAL"),
                ("REUSED",),
                ("FAIL", "PASS"),
            ),
            (
                "structural",
                ("UNEARNED_MODULE",),
                ("REUSED",),
                ("FAIL", "PASS"),
            ),
            (
                "questionable",
                ("QUESTIONABLE_OTHER",),
                ("REUSED",),
                ("WARNING", "PASS"),
            ),
            ("duplicated", (), ("DUPLICATED",), ("PASS", "FAIL")),
            ("bypassed", (), ("BYPASSED",), ("PASS", "FAIL")),
            (
                "near-duplicate",
                (),
                ("NEAR_DUPLICATE",),
                ("PASS", "WARNING"),
            ),
            (
                "indeterminate",
                (),
                ("INDETERMINATE",),
                ("PASS", "WARNING"),
            ),
            ("missing-reuse", (), (), ("PASS", "WARNING")),
            (
                "no-reuse-available",
                (),
                ("NO_REUSE_AVAILABLE",),
                ("PASS", "PASS"),
            ),
        )
        for name, yagni, reuse, expected in cases:
            with self.subTest(name=name):
                code = self.module.validate_code_judgment(
                    self.packet,
                    self.valid_code_response(
                        yagni_items=yagni, reuse_items=reuse
                    ),
                )
                decision = self.module.aggregate(
                    code, self.reconcile(), self.rules
                )
                self.assertEqual(
                    (decision.yagni, decision.reuse), expected
                )

    def test_rule_pack_rejects_non_v1_and_malformed_policy(self):
        source = json.loads(RULES.read_text(encoding="utf-8"))
        mutations = {}
        for field in ("schema_version", "report_schema_version"):
            for value in (2, 1.0):
                changed = json.loads(json.dumps(source))
                changed[field] = value
                mutations[
                    f"{field}.*version 1(?#unsupported={value})"
                ] = changed

        changed = json.loads(json.dumps(source))
        changed["statuses"]["clause"].append("MAYBE")
        mutations["statuses.*closed v1"] = changed

        changed = json.loads(json.dumps(source))
        changed["routes"]["PASS"] = ["qa-ticket"]
        mutations["routes.PASS.*conditional"] = changed

        changed = json.loads(json.dumps(source))
        changed["routes"]["FIDELITY_FAIL"] = {
            "acceptance_qa_exists": ["qa-pr"],
            "otherwise": ["qa-ticket"],
        }
        mutations["routes.FIDELITY_FAIL.*fixed"] = changed

        changed = json.loads(json.dumps(source))
        changed["semantic_contract"]["status_meanings"]["unknown"] = "MET"
        mutations["semantic_contract.status_meanings.*extra.*keys"] = changed

        changed = json.loads(json.dumps(source))
        changed["semantic_contract"]["status_meanings"][
            "upper_bound_breach"
        ] = "UNMET"
        mutations["semantic_contract.*closed v1"] = changed

        changed = json.loads(json.dumps(source))
        changed["semantic_contract"]["reuse"][
            "contrary_requires_issued_fact"
        ] = 1
        mutations["semantic_contract.*closed v1.*type"] = changed

        for message, document in mutations.items():
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "rules.json"
                    path.write_text(json.dumps(document), encoding="utf-8")
                    with self.assertRaisesRegex(
                        self.module.AuditInputError, message
                    ):
                        self.module.load_rules(path)

    def test_public_facade_reexports_focused_module_boundaries(self):
        domain = importlib.import_module("audit_domain")
        validation = importlib.import_module("audit_validation")
        policy = importlib.import_module("audit_policy")

        self.assertIs(self.module.RulePack, domain.RulePack)
        self.assertIs(self.module.CodeJudgment, domain.CodeJudgment)
        self.assertIs(self.module.Finding, domain.Finding)
        self.assertIs(self.module.load_rules, domain.load_rules)
        self.assertIs(
            self.module.validate_code_judgment,
            validation.validate_code_judgment,
        )
        self.assertIs(self.module.aggregate, policy.aggregate)

    def test_policy_domain_objects_are_immutable(self):
        code = self.module.validate_code_judgment(
            self.packet, self.valid_code_response()
        )
        decision = self.module.aggregate(
            code, self.reconcile(), self.rules
        )

        for value in (self.rules, code, decision):
            with self.subTest(type=type(value).__name__):
                self.assertTrue(dataclasses.is_dataclass(value))
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    value.schema_version = 2


if __name__ == "__main__":
    unittest.main()
