import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.lower().split())


class CleanUpSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat_body = normalized(self.body)

    def test_invocation_authorizes_in_scope_repairs_without_routine_pauses(self):
        for phrase in (
            "invocation is authority",
            "valid in-scope fixes",
            "focused commits",
            "risk-first",
            "remaining scope",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

        for forbidden in (
            "confirm the resolved branch",
            "offer to scope",
            "show the triage to the user",
            "/pi-review",
            "/be-pr",
            "/frontend-pr",
        ):
            self.assertNotIn(normalized(forbidden), self.flat_body)

    def test_target_resolution_records_pr_metadata_and_ambiguous_candidate_facts(self):
        for phrase in (
            "pr metadata",
            "baseRefName",
            "candidate facts",
            "ambiguous target",
            "do not ask the user to select",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_pr_resolution_handles_all_candidates_instead_of_first_match(self):
        start = self.body.index("## Step 2: Identify the diff")
        end = self.body.index("## Step 3: Run the review lenses portably")
        resolution = normalized(self.body[start:end])

        for phrase in (
            "full candidate metadata",
            "number",
            "url",
            "head",
            "base",
            "candidate count",
            "all candidate facts",
            "multiple or conflicting candidates",
        ):
            self.assertIn(normalized(phrase), resolution)

        self.assertNotIn(".[0]", resolution)

    def test_large_diffs_are_sliced_automatically_and_remaining_scope_is_reported(self):
        for phrase in (
            "2,000 changed lines",
            "coherent slices",
            "risk-first",
            "unprocessed scope",
            "remaining scope",
            "do not pause",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_four_review_lenses_and_test_first_repair_loop_remain(self):
        for phrase in (
            "Code reuse",
            "Code quality",
            "Efficiency",
            "Coverage",
            "RED",
            "GREEN",
            "TDD",
            "one focused commit per finding",
            "cumulative diff",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_review_and_final_pass_are_runtime_portable(self):
        for phrase in (
            "current runtime's actual subagent interface",
            "perform each missing lens directly",
            "skill, command, agent, or plugin",
            "perform the same contract directly",
            "delegated or direct",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

        for forbidden in (
            "/simplify",
            "/find-skills",
            "plugin cache",
            "luna",
            "terra",
            "deepseek",
            "glm",
        ):
            self.assertNotIn(normalized(forbidden), self.flat_body)

    def test_handoff_uses_opening_prs_and_keeps_no_push_no_pr_boundary(self):
        self.assertIn("opening-prs", self.flat_body)
        for phrase in (
            "must not push",
            "must not open a pull request",
            "hand back to the human",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_behavior_cases_cover_large_diff_and_ambiguous_target(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "clean-up")
        self.assertEqual(
            {case["id"] for case in payload["evals"]},
            {
                "large-diff-risk-first",
                "ambiguous-target-candidate-facts",
                "runtime-capability-fallback",
            },
        )

        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertTrue(case["expectations"])

        large_diff = next(
            case for case in payload["evals"] if case["id"] == "large-diff-risk-first"
        )
        large_diff_text = normalized(
            " ".join([large_diff["prompt"], large_diff["expected_output"]] + large_diff["expectations"])
        )
        for phrase in (
            "2,500-line branch",
            "five valid findings",
            "risk-first coherent slices",
            "no scope-choice prompt",
            "unprocessed scope",
        ):
            self.assertIn(normalized(phrase), large_diff_text)

        ambiguous = next(
            case
            for case in payload["evals"]
            if case["id"] == "ambiguous-target-candidate-facts"
        )
        ambiguous_text = normalized(
            " ".join([ambiguous["prompt"], ambiguous["expected_output"]] + ambiguous["expectations"])
        )
        self.assertIn("candidate facts", ambiguous_text)
        self.assertIn("do not ask the user to select", ambiguous_text)

        fallback = next(
            case
            for case in payload["evals"]
            if case["id"] == "runtime-capability-fallback"
        )
        fallback_text = normalized(
            " ".join(
                [fallback["prompt"], fallback["expected_output"]]
                + fallback["expectations"]
            )
        )
        for phrase in (
            "no installed simplification skill",
            "one reviewer fails",
            "perform the missing review directly",
            "do not stop",
            "do not search",
        ):
            self.assertIn(normalized(phrase), fallback_text)


if __name__ == "__main__":
    unittest.main()
