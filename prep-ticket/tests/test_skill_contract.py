import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.lower().split())


class PrepTicketSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat_body = normalized(self.body)

    def test_missing_ticket_uses_repository_only_evidence_without_inventing_requirements(self):
        for phrase in (
            "ticket id is optional",
            "repository-only mode",
            "ticket context unavailable",
            "exact lookup failure",
            "repository/diff evidence",
            "do not invent requirements or acceptance criteria",
            "exactly one lazy evidence-backed suggested approach",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_missing_ticket_does_not_start_question_loops(self):
        for forbidden in (
            "what's the ticket id",
            "ask the user for the ticket id",
            "ask the user to verify the ticket id",
            "ask user to verify the ticket id",
        ):
            self.assertNotIn(normalized(forbidden), self.flat_body)

    def test_repository_only_probes_provider_and_preserves_exact_failure_metadata(self):
        for phrase in (
            "provider availability probe",
            "command -v <provider>",
            "linear --version",
            "jira version",
            "capture and report the exact probe command, stdout, stderr, and exit status as separate fields",
            "normalized missing error",
            "linear: command not found",
            "without attempting a ticket lookup",
            "ticket lookup: not attempted — no ticket id",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_repository_only_report_separates_provider_probe_and_ticket_lookup(self):
        for phrase in (
            "**provider probe**",
            "**ticket lookup**",
        ):
            self.assertIn(normalized(phrase), self.flat_body)
        self.assertNotIn(normalized("**lookup**"), self.flat_body)

    def test_repository_only_discovers_committed_staged_and_unstaged_changes(self):
        for phrase in (
            "committed branch changes",
            "git merge-base",
            "git diff <base>...head",
            "staged changes",
            "git diff --cached",
            "unstaged changes",
        ):
            self.assertIn(normalized(phrase), self.flat_body)

    def test_behavior_case_covers_missing_ticket_repository_only_mode(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "prep-ticket")
        self.assertEqual(
            [case["id"] for case in payload["evals"]],
            ["missing-ticket-repository-only"],
        )

        case = payload["evals"][0]
        self.assertTrue(case["prompt"].strip())
        self.assertTrue(case["expected_output"].strip())
        self.assertTrue(case["expectations"])
        case_text = normalized(
            " ".join(
                [case["prompt"], case["expected_output"]] + case["expectations"]
            )
        )
        for phrase in (
            "no ticket pattern",
            "unavailable provider cli",
            "repository-only mode",
            "ticket context unavailable",
            "exact lookup failure",
            "linear: command not found",
            "not invent",
            "exactly one",
            "evidence-backed",
            "do not ask for a ticket id",
        ):
            self.assertIn(normalized(phrase), case_text)


if __name__ == "__main__":
    unittest.main()
