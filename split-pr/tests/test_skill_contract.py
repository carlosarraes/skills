import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.lower().split())


class SplitPrSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.frontmatter = self.skill.split("---", 2)[1]
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat_body = normalized(self.body)

    def test_skill_remains_model_visible_and_describes_policy_trigger(self):
        self.assertNotIn("disable-model-invocation", self.frontmatter)
        description = normalized(self.frontmatter)
        for phrase in (
            "repository size limits",
            "mondrio",
            "over 1,000 changed lines",
        ):
            self.assertIn(normalized(phrase), description)

    def test_invocation_or_enforced_violation_authorizes_split_without_second_gate(self):
        for phrase in (
            "direct invocation or an observed enforced repository size-policy violation authorizes",
            "without a second approval",
            "show the plan before mutation",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

        for forbidden in (
            "Proceed?",
            "wait for approval",
            "Checkpoint",
            "stamp-check",
            "review-swarm",
        ):
            self.assertNotIn(normalized(forbidden), self.flat_body)

    def test_mondrio_threshold_is_strictly_over_one_thousand(self):
        for phrase in (
            "1,001 changed lines",
            "strictly greater than 1,000",
            "1,000 changed lines does not trigger",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_original_identity_and_new_branch_safety_are_recorded(self):
        for phrase in (
            "original branch",
            "exact SHA",
            "only new stack branches",
            "never rewrite",
            "never reset",
            "never force-push the original branch",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_layer_materialization_stages_selected_changes_before_commit(self):
        restore = self.body.index("git restore --source=<original-branch>")
        commit_command = 'git commit -m "<type>(<scope>): <layer 1 description>"'
        commit = self.body.index(commit_command, restore) + len(commit_command)
        materialization = normalized(self.body[restore:commit])

        self.assertIn("git restore --source=<original-branch> --staged --worktree -p", materialization)
        self.assertIn("git diff --cached --check", materialization)
        self.assertIn("git diff --cached --name-only", materialization)
        self.assertLess(materialization.index("--staged --worktree"), materialization.index("git diff --cached"))
        self.assertLess(materialization.index("git diff --cached"), materialization.index("git commit"))

    def test_each_layer_checks_non_mutating_mergeability_against_intended_parent(self):
        start = self.body.index("### Step 5: Verify every layer independently")
        end = self.body.index("### Step 6: Publish and open the stack", start)
        verification = normalized(self.body[start:end])

        for phrase in (
            "mergeability",
            "intended parent",
            "git merge-tree --write-tree <intended-parent> <layer-commit>",
            "non-mutating",
            "conflict",
            "build",
            "tests",
            "runtime",
        ):
            self.assertIn(normalized(phrase), verification)
        self.assertLess(verification.index("git merge-tree"), verification.index("repository build"))

    def test_each_layer_is_verified_independently(self):
        for phrase in (
            "verify every layer independently",
            "build",
            "tests",
            "runtime",
            "observed outcomes",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_cohesive_oversize_change_stops_without_artificial_split(self):
        for phrase in (
            "cohesive",
            "no safe seam",
            "bounded size-policy explanation",
            "artificial split",
            "stop",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_behavior_cases_cover_automatic_split_and_bounded_stop(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "split-pr")
        self.assertEqual(
            {case["id"] for case in payload["evals"]},
            {
                "mondrio-automatic-separable",
                "cohesive-no-safe-seam-stop",
                "mondrio-exact-cap-near-miss",
            },
        )
        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertTrue(case["expectations"])

        separable = next(
            case for case in payload["evals"] if case["id"] == "mondrio-automatic-separable"
        )
        separable_text = normalized(
            " ".join([separable["prompt"], separable["expected_output"]] + separable["expectations"])
        )
        for phrase in (
            "mondrio",
            "1,001 changed lines",
            "separable seams",
            "automatic",
            "without a second approval",
        ):
            self.assertIn(normalized(phrase), separable_text)

        cohesive = next(
            case for case in payload["evals"] if case["id"] == "cohesive-no-safe-seam-stop"
        )
        cohesive_text = normalized(
            " ".join([cohesive["prompt"], cohesive["expected_output"]] + cohesive["expectations"])
        )
        for phrase in (
            "cohesive",
            "1,001 changed lines",
            "no safe seam",
            "bounded size-policy explanation",
            "rather than artificial splitting",
        ):
            self.assertIn(normalized(phrase), cohesive_text)

        near_miss = next(
            case for case in payload["evals"] if case["id"] == "mondrio-exact-cap-near-miss"
        )
        near_miss_prompt = normalized(near_miss["prompt"])
        for forbidden in (
            "must not auto-trigger",
            "does not auto-trigger",
            "no automatic split",
            "not an automatic trigger",
            "near-miss",
            "expect no automatic",
        ):
            self.assertNotIn(normalized(forbidden), near_miss_prompt)

        near_miss_text = normalized(
            " ".join([near_miss["prompt"], near_miss["expected_output"]] + near_miss["expectations"])
        )
        for phrase in (
            "mondrio",
            "exactly 1,000 changed lines",
            "not an automatic trigger",
            "does not automatically invoke split-pr",
            "leaves the branch and refs unchanged",
        ):
            self.assertIn(normalized(phrase), near_miss_text)


if __name__ == "__main__":
    unittest.main()
