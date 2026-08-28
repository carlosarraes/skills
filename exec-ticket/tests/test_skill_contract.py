import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


class ExecTicketSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.normalized_body = " ".join(self.body.lower().split())

    def assert_ordered(self, *phrases):
        positions = [self.body.find(phrase) for phrase in phrases]
        self.assertNotIn(-1, positions, phrases)
        self.assertEqual(positions, sorted(positions), phrases)

    def test_workflow_has_five_ordered_phases(self):
        self.assert_ordered(
            "## Phase 1: Resolve context",
            "## Phase 2: Load authority",
            "## Phase 3: Record reuse decisions",
            "## Phase 4: Implement one behavior at a time",
            "## Phase 5: Verify and report",
        )

    def test_context_and_authority_use_local_evidence_when_provider_is_missing(self):
        for phrase in (
            "ticket and branch context",
            "repository instructions",
            "prep-ticket evidence",
            "available plan",
            "repository and current user intent outrank stale plans",
            "If the ticket provider is unavailable",
            "continue from sufficient repository, diff, and plan evidence",
            "record the provider gap in the report",
        ):
            self.assertIn(phrase.lower(), self.normalized_body)

    def test_lazy_reuse_order_and_one_decision_per_responsibility_are_required(self):
        self.assert_ordered(
            "existing helper/module",
            "native / stdlib / platform feature",
            "already-installed dependency",
            "few lines of new code",
            "new structure",
        )
        for phrase in (
            "one reuse decision per implementation responsibility",
            "file:line",
            "compatible or incompatible with evidence",
            "Reuse every compatible existing helper",
            "Do not begin RED until every responsibility has a decision",
            "working notes or the transcript",
        ):
            self.assertIn(phrase.lower(), self.normalized_body)

    def test_implementation_is_one_behavior_per_red_green_refactor_loop(self):
        self.assert_ordered(
            "RED",
            "GREEN",
            "REFACTOR",
        )
        for phrase in (
            "one observable behavior at a time",
            "write its behavior test",
            "run it and confirm the expected failure",
            "before writing its implementation",
            "make the smallest change that passes",
            "refactor only while green",
            "no speculative abstraction or dependency",
        ):
            self.assertIn(phrase.lower(), self.normalized_body)

    def test_material_outcome_change_stops_before_encoding_and_returns_to_design(self):
        for phrase in (
            "materially changes the requested user-visible outcome",
            "stop before writing tests or source that encode the changed outcome",
            "report the discovery and the decision required",
            "return to the normal design process",
        ):
            self.assertIn(phrase.lower(), self.normalized_body)

    def test_verification_and_report_include_focused_full_and_behavior_mapping(self):
        self.assert_ordered(
            "focused test suite",
            "full test suite",
            "final report",
        )
        for phrase in (
            "all green is the bar",
            "behaviors implemented, with the test that pins each",
            "files changed",
            "suite results",
        ):
            self.assertIn(phrase.lower(), self.normalized_body)

    def test_contract_workflow_terms_are_absent(self):
        for forbidden in (
            "change-contract",
            "check-contract",
            "current.json",
            "approval",
            "ledger",
            "contract root",
            "contract mode",
            "legacy mode",
        ):
            self.assertNotIn(forbidden, self.normalized_body)

    def test_behavior_evals_cover_operational_and_migration_cases(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "exec-ticket")
        self.assertEqual(
            [case["id"] for case in payload["evals"]],
            [
                "settled-plan-without-contract-files",
                "missing-ticket-provider-with-local-evidence",
                "material-outcome-change-stops-design",
                "persistent-migration-invariants",
            ],
        )
        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertIsInstance(case["expectations"], list)
            self.assertTrue(case["expectations"])

        first, second, third, fourth = payload["evals"]
        self.assertIn("continues without approval artifacts", first["expected_output"])
        self.assertIn("continues without approval artifacts", second["expected_output"])
        self.assertIn("stops before writing tests or source", third["expected_output"])
        self.assertIn("decision required", third["expected_output"])
        self.assertIn("interrupted execution", fourth["expected_output"])
        self.assertIn("deletes the legacy API", fourth["expected_output"])


if __name__ == "__main__":
    unittest.main()
