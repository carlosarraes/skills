import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


class CheckDataSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat_body = " ".join(self.body.lower().split())

    def assert_ordered(self, *phrases):
        positions = [self.body.find(phrase) for phrase in phrases]
        self.assertNotIn(-1, positions, phrases)
        self.assertEqual(positions, sorted(positions), phrases)

    def test_workflow_orders_discovery_plan_seed_verify_and_report(self):
        self.assert_ordered(
            "## Step 1: Discover context",
            "## Step 2: Plan data",
            "## Step 3: Seed data",
            "## Step 4: Verify counts",
            "## Step 5: Report",
        )

    def test_plan_only_stops_before_seed_mutation(self):
        plan = self.body.index("## Step 2: Plan data")
        plan_only = self.body.index("plan-only", plan)
        seed = self.body.index("## Step 3: Seed data")
        self.assertLess(plan, plan_only)
        self.assertLess(plan_only, seed)
        plan_to_seed = self.body[plan:seed].lower()
        self.assertIn("stop", plan_to_seed)
        self.assertIn("no database mutation", plan_to_seed)

    def test_seed_contract_preserves_idempotency_order_and_accounting(self):
        for phrase in (
            "natural-key match",
            "seed tag",
            "FK parents first",
            "before",
            "inserted",
            "skipped",
            "failed",
            "after",
        ):
            self.assertIn(phrase.lower(), self.flat_body)

    def test_planning_contract_keeps_schema_aware_four_bucket_rows(self):
        for phrase in (
            "Happy path",
            "Edge cases",
            "Error paths",
            "Stupid paths",
            "schema",
            "NOT NULL",
            "CHECK",
            "FK",
            "concrete shape",
            "why",
        ):
            self.assertIn(phrase.lower(), self.flat_body)

    def test_old_split_seed_entrypoint_is_not_instructed(self):
        self.assertNotIn("/seed-data", self.body)

    def test_behavior_cases_cover_default_and_plan_only_branches(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "check-data")
        self.assertEqual(
            [case["id"] for case in payload["evals"]],
            ["default-plan-seed-verify", "plan-only"],
        )

        default, plan_only = payload["evals"]
        self.assertIn("idempotent insertion", default["expected_output"])
        self.assertIn("before/after verification", default["expected_output"])
        self.assertIn("continues from the written plan", default["expected_output"])
        self.assertIn("stops after writing the plan", plan_only["expected_output"])
        self.assertIn("no database mutation", plan_only["expected_output"])
        for case in (default, plan_only):
            self.assertIsInstance(case["prompt"], str)
            self.assertTrue(case["prompt"].strip())
            self.assertIsInstance(case["expectations"], list)
            self.assertTrue(case["expectations"])


if __name__ == "__main__":
    unittest.main()
