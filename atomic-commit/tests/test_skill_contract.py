import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


class AtomicCommitSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]

    def test_invocation_is_authority_and_plan_runs_without_second_gate(self):
        for phrase in (
            "Invocation is commit authority",
            "Record the plan",
            "included in the final record",
            "execute immediately",
        ):
            self.assertIn(phrase, self.body)
        for forbidden in (
            "Proceed with this commit plan?",
            "yes / edit / abort",
            "ask the user how to proceed",
        ):
            self.assertNotIn(forbidden, self.body)

    def test_execution_uses_explicit_paths_and_preserves_failed_hook_state(self):
        for phrase in (
            "Stage each commit using explicit paths",
            "git add path/to/file1 path/to/file2",
            "A hook failure ends the run with the command, output, staged paths, and worktree status",
            "preserve the index and worktree state",
        ):
            self.assertIn(phrase, self.body)

    def test_behavior_case_covers_invocation_authority(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "atomic-commit")
        self.assertEqual(
            [case["id"] for case in payload["evals"]],
            ["invocation-authorizes-commit"],
        )
        case = payload["evals"][0]
        self.assertIn("does not ask whether to proceed", case["expectations"])
        self.assertIn("stages explicit paths", case["expectations"])
        self.assertIn("creates focused conventional commits", case["expectations"])
        self.assertIn("stops and reports exact state after a failed hook", case["expectations"])


if __name__ == "__main__":
    unittest.main()
