import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
CAMPAIGN = ROOT / "references" / "campaign.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.lower().split())


class TestAuditSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat_body = normalized(self.body)
        self.campaign = CAMPAIGN.read_text(encoding="utf-8")
        self.flat_campaign = normalized(self.campaign)

    def test_one_value_bar_serves_authoring_audit_and_campaign_modes(self):
        for phrase in (
            "three modes, one value bar",
            "authoring mode gates every new or changed test at write time",
            "audit mode runs focused sweeps",
            "campaign mode prunes one whole subsystem's test surface",
            "references/campaign.md",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_authoring_gate_requires_four_answers_and_rejects_junk(self):
        for phrase in (
            "before adding any test, answer four questions",
            "observable behavior, invariant, or independent contract does it protect",
            "credible regression makes it fail",
            "why does existing coverage not already catch that failure",
            "production seam",
            "move the test to the real boundary",
            "check the test against every",
            "junk pattern",
            "bug regression tests must fail on the pre-fix code",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_junk_patterns_and_retention_bar_remain_the_shared_contract(self):
        for phrase in (
            "assertion-free coverage probes",
            "copied fixtures, inventories, manifests, or export lists",
            "exact source, import, or string greps",
            "tests whose only purpose is preserving test-only exports",
            "expected values produced by the helper or renderer under test",
            "negative controls that pass for an unrelated reason",
            "public API",
            "source inspection when it is the cheapest independent guard",
            "static or slow is not a deletion reason",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_candidate_evidence_is_complete_before_deletion(self):
        for phrase in (
            "exact test name and location",
            "what failure it can actually detect",
            "non-test callers of the covered production or support seam",
            "stronger remaining owner-boundary proof",
            "production or test-support deletion unlocked",
            "risk and the focused validation command",
            "one coherent owner-boundary batch",
            "net-negative production loc",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_validation_and_landing_are_repository_portable_and_authorized(self):
        for phrase in (
            "never edit source or tests while a test runner is watching the checkout",
            "the repository's focused command",
            "git diff --check",
            "repository's changed-path gate",
            "git diff --numstat",
            "report production and tooling lines separately",
            "clean-up",
            "opening-prs",
            "pr-sweep",
            "only when authorized",
            "one coherent pr at a time",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

        for forbidden in (
            "openclaw",
            "crabbox",
            "run-vitest",
            "check-changed.mjs",
            "autoreview",
            "pr-maintainer",
        ):
            self.assertNotIn(normalized(forbidden), self.flat_body)

    def test_handoff_reports_value_and_loc_without_rewriting_implementations(self):
        for phrase in (
            "root cause and removed low-value categories",
            "retained false positives and why they remain valuable",
            "production versus test loc",
            "named follow-ups",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

        self.assertIn(
            normalized("do not convert uncertain candidates into cleanup"),
            self.flat_body,
        )

    def test_campaign_orders_baseline_through_handoff_with_completion_criteria(self):
        steps = (
            "## 1. baseline",
            "## 2. lanes and inventory",
            "## 3. read-only ledger per lane",
            "## 4. layer plan per lane",
            "## 5. cutover",
            "## 6. preservation review",
            "## 7. product defects",
            "## 8. reconcile and hand off",
        )
        positions = [self.flat_campaign.find(step) for step in steps]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))
        self.assertGreaterEqual(self.flat_campaign.count("done when"), 7)
        self.assertIn("do not start the next step early", self.flat_campaign)

    def test_campaign_preservation_review_mutates_and_restores_the_owner(self):
        for phrase in (
            "of the production owner and confirm the keeper goes red",
            "restore the source byte for byte",
            "new assertions that cannot fail",
            "rejection row the production code never reaches",
            "failing control",
            "passing candidate",
        ):
            self.assertIn(normalized(phrase), self.flat_campaign)

        for forbidden in (
            "openclaw",
            "crabbox",
            "run-vitest",
            "check-changed.mjs",
            "telegram",
        ):
            self.assertNotIn(normalized(forbidden), self.flat_campaign)

    def test_behavior_cases_cover_authoring_audit_and_campaign(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "test-audit")
        self.assertEqual(
            {case["id"] for case in payload["evals"]},
            {
                "authoring-gate-rejects-junk",
                "audit-candidate-requires-evidence",
                "campaign-preservation-mutation",
            },
        )

        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertTrue(case["expectations"])

        authoring = next(
            case
            for case in payload["evals"]
            if case["id"] == "authoring-gate-rejects-junk"
        )
        authoring_text = normalized(
            " ".join(
                [authoring["prompt"], authoring["expected_output"]]
                + authoring["expectations"]
            )
        )
        for phrase in (
            "four authoring questions",
            "junk pattern",
            "real boundary",
            "production-only export",
        ):
            self.assertIn(normalized(phrase), authoring_text)

        candidate = next(
            case
            for case in payload["evals"]
            if case["id"] == "audit-candidate-requires-evidence"
        )
        candidate_text = normalized(
            " ".join(
                [candidate["prompt"], candidate["expected_output"]]
                + candidate["expectations"]
            )
        )
        for phrase in (
            "candidate evidence",
            "test-only production seam",
            "stronger remaining owner-boundary proof",
            "production loc separately",
        ):
            self.assertIn(normalized(phrase), candidate_text)

        campaign = next(
            case
            for case in payload["evals"]
            if case["id"] == "campaign-preservation-mutation"
        )
        campaign_text = normalized(
            " ".join(
                [campaign["prompt"], campaign["expected_output"]]
                + campaign["expectations"]
            )
        )
        for phrase in (
            "deliberate production mutation",
            "keeper red",
            "restore the source byte for byte",
            "failing control",
            "passing candidate",
        ):
            self.assertIn(normalized(phrase), campaign_text)


if __name__ == "__main__":
    unittest.main()
