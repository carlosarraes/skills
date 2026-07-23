import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL = ROOT / "references" / "contract-protocol.md"


def normalized(text):
    return " ".join(text.split()).lower()


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

    def test_state_commands_are_location_independent(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertNotIn(
            "python change-contract/scripts/contract_state.py",
            text,
        )
        self.assertIn(
            "python <skill-dir>/scripts/contract_state.py approve",
            text,
        )
        self.assertIn(
            "python <skill-dir>/scripts/contract_state.py verify",
            text,
        )

    def test_producer_uses_the_protocol_branch_directory_root(self):
        text = SKILL.read_text(encoding="utf-8")
        flattened = normalized(text)

        self.assertIn(
            normalized(
                "derive `<branch-dir>` using the protocol sanitizer already read"
            ),
            flattened,
        )
        self.assertEqual(
            text.count("--root <notes-root>/<branch-dir>/contract"),
            2,
        )
        self.assertNotIn("--root <notes-root>/<branch>/contract", text)
        self.assertNotIn(
            're.sub(r"[^A-Za-z0-9._-]+"',
            text,
        )

    def test_state_helper_runs_from_a_foreign_working_directory(self):
        helper = ROOT / "scripts" / "contract_state.py"
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [sys.executable, str(helper), "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("approve", result.stdout)
        self.assertIn("verify", result.stdout)

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
