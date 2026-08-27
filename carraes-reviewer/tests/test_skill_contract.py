import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"


class CarraesReviewerSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.frontmatter, self.body = self.skill.split("\n---\n", 1)

    def test_skill_is_user_only_with_exact_review_description(self):
        self.assertIn(
            "description: Use only when explicitly invoked to review a PR or diff "
            "in Carlos Arraes's voice.",
            self.frontmatter,
        )
        self.assertIn("disable-model-invocation: true", self.frontmatter)

    def test_posting_gate_still_requires_draft_approval_and_verbatim_text(self):
        for phrase in (
            "full set of comments it wants to leave",
            "Show Carlos the draft",
            "ask for approval",
            "Post only what he approved",
            "verbatim",
        ):
            self.assertIn(phrase, self.body)

    def test_deleted_reviewer_route_is_absent_from_delegated_review_contract(self):
        self.assertNotIn("review-swarm", self.body)
        for phrase in (
            "delegated sub-reviewer",
            "structured findings",
            "does **not** post",
        ):
            self.assertIn(phrase, self.body)


if __name__ == "__main__":
    unittest.main()
