import dataclasses
import importlib.util
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
    spec = importlib.util.spec_from_file_location("audit_runtime", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
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
            "clause_ids": ["O1", "B1", "I1", "C1", "A-B1", "S1"],
            "changed_path_ids": ["P1"],
            "evidence_ids": [
                "behavior:O1",
                "behavior:B1",
                "risk:I1",
                "public-contract:C1",
                "acceptance:A-B1",
                "surface:P1",
                "complexity:P1",
                "reuse:P1",
            ],
        }

    def valid_code_response(
        self,
        *,
        owned=None,
        surface="MET",
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
        return {
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
