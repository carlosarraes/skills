import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL = ROOT / "references" / "contract-protocol.md"


class SkillContractTests(unittest.TestCase):
    def test_user_invoked_frontmatter(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: change-contract", text)
        self.assertIn("disable-model-invocation: true", text)

    def test_each_step_has_a_completion_criterion(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertEqual(text.count("### Step "), 5)
        self.assertEqual(text.count("**Complete when:**"), 5)

    def test_skill_points_to_single_protocol(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("references/contract-protocol.md", text)
        self.assertIn("scripts/contract_state.py approve", text)

    def test_protocol_contains_required_contract_sections(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for heading in (
            "## Required behaviors",
            "## Explicit non-goals",
            "## Invariants and risk boundaries",
            "## Reuse evidence",
            "## Expected change surface",
            "## Complexity budget",
            "## Acceptance evidence",
            "## Unresolved decisions",
        ):
            self.assertIn(heading, text)

    def test_protocol_defines_yagni_order_and_drift_classes(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for phrase in (
            "existing helper or module",
            "native, standard-library, or platform capability",
            "already-installed dependency",
            "a few lines of new code",
            "new structure",
            "Implementation detail",
            "Bounded deviation",
            "Contract deviation",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
