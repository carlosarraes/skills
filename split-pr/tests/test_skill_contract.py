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

    def test_mergeability_rows_are_literal_audited_and_repeated_in_final_report(self):
        row = (
            "Mergeability: git merge-tree --write-tree <intended-parent> <layer-commit> "
            "| exit: <status> | conflicts: <none-or-details> | output: <observed-output>"
        )
        verification_start = self.body.index("### Step 5: Verify every layer independently")
        report_start = self.body.index("### Step 7: Report the result")
        verification = normalized(self.body[verification_start:report_start])
        report = normalized(self.body[report_start:])

        self.assertIn(normalized(row), verification)
        self.assertIn("before build/test/runtime evidence", verification)
        for phrase in (
            "would-run",
            "unobserved",
            "never claim execution",
            "missing command, exit, conflict, or output field",
            "makes report incomplete",
            "must be corrected",
        ):
            self.assertIn(normalized(phrase), verification + " " + report)
        self.assertIn(normalized(row), report)
        self.assertIn("for every layer", report)

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
        mergeability_expectations = [
            normalized(expectation)
            for expectation in separable["expectations"]
            if "mergeability" in normalized(expectation)
        ]
        self.assertTrue(mergeability_expectations)
        mergeability_text = " ".join(mergeability_expectations)
        for phrase in (
            "for each layer",
            "non-mutating",
            "mergeability",
            "intended parent",
            "conflict evidence",
        ):
            self.assertIn(normalized(phrase), mergeability_text)
        row = (
            "Mergeability: git merge-tree --write-tree <intended-parent> <layer-commit> "
            "| exit: <status> | conflicts: <none-or-details> | output: <observed-output>"
        )
        separable_rubric = normalized(
            " ".join([separable["expected_output"]] + separable["expectations"])
        )
        for phrase in (
            row,
            "one exact mergeability row for every layer in the final report",
            "before build/test/runtime evidence",
            "would-run/unobserved placeholders",
            "never claims execution",
            "missing command, exit, conflict, or output field",
        ):
            self.assertIn(normalized(phrase), separable_rubric)

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
        for phrase in (
            "no direct split-pr invocation was supplied",
            "only signal is the observed automatic policy check",
        ):
            self.assertIn(normalized(phrase), near_miss_prompt)
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
        self.assertIn(
            normalized("does not automatically invoke split-pr"),
            normalized(near_miss["expected_output"]),
        )

    def test_behavior_prompts_are_neutral_while_rubrics_keep_required_actions(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        separable = next(
            case for case in payload["evals"] if case["id"] == "mondrio-automatic-separable"
        )
        separable_prompt = normalized(separable["prompt"])
        for phrase in (
            "mondrio",
            "1,001 changed lines",
            "repository size-policy check",
            "separable seams",
        ):
            self.assertIn(normalized(phrase), separable_prompt)
        for forbidden in (
            "expect automatic use",
            "without a second approval",
            "visible plan before mutation",
            "original branch and exact sha recorded",
            "only new stack branches",
            "independent verification of every layer",
            "mergeability",
            "complete split-pr action trace",
        ):
            self.assertNotIn(normalized(forbidden), separable_prompt)

        separable_rubric = normalized(
            " ".join([separable["expected_output"]] + separable["expectations"])
        )
        for phrase in (
            "split automatically",
            "without a second approval",
            "original branch and exact sha",
            "only new stack branches",
            "for each layer",
            "non-mutating merge-tree",
            "intended parent",
            "conflict evidence",
        ):
            self.assertIn(normalized(phrase), separable_rubric)

        cohesive = next(
            case for case in payload["evals"] if case["id"] == "cohesive-no-safe-seam-stop"
        )
        cohesive_prompt = normalized(cohesive["prompt"])
        for phrase in (
            "cohesive mondrio",
            "1,001 changed lines",
            "enforced 1,000-line repository size limit",
            "no independently runnable safe seam",
        ):
            self.assertIn(normalized(phrase), cohesive_prompt)
        for forbidden in (
            "expect a bounded stop",
            "bounded size-policy explanation",
            "no artificial split",
            "no new branches",
            "before any mutation",
        ):
            self.assertNotIn(normalized(forbidden), cohesive_prompt)

        cohesive_rubric = normalized(
            " ".join([cohesive["expected_output"]] + cohesive["expectations"])
        )
        for phrase in (
            "stops before mutation",
            "bounded size-policy explanation",
            "no safe seam",
            "does not manufacture artificial layers",
        ):
            self.assertIn(normalized(phrase), cohesive_rubric)


if __name__ == "__main__":
    unittest.main()
