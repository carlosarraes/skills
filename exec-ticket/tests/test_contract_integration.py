import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL_ROOT = ROOT.parent / "change-contract"
PROTOCOL = PROTOCOL_ROOT / "references" / "contract-protocol.md"
HELPER = PROTOCOL_ROOT / "scripts" / "contract_state.py"
MATERIALIZER = ROOT / "evals" / "materialize_fixture.py"


def sanitize_branch(branch):
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", branch)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value or value in {".", ".."}:
        raise ValueError("unsafe empty branch directory")
    return value


def normalized(text):
    return " ".join(text.split()).lower()


class ContractIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.protocol = PROTOCOL.read_text(encoding="utf-8")
        self.skill_normalized = normalized(self.skill)
        self.protocol_normalized = normalized(self.protocol)

    def assert_ordered(self, text, *phrases):
        text = normalized(text)
        positions = [text.index(normalized(phrase)) for phrase in phrases]
        self.assertEqual(positions, sorted(positions), phrases)

    def materialize_contract_repo(self, destination):
        subprocess.run(
            [
                sys.executable,
                str(MATERIALIZER),
                "contract-repo",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_protocol_defines_one_deterministic_branch_sanitizer(self):
        self.assertEqual(
            {
                branch: sanitize_branch(branch)
                for branch in (
                    "feature/proj-123",
                    "Feature//MON 123",
                    "-release---v1.2_hotfix-",
                )
            },
            {
                "feature/proj-123": "feature-proj-123",
                "Feature//MON 123": "Feature-PROJ-123",
                "-release---v1.2_hotfix-": "release-v1.2_hotfix",
            },
        )
        for branch in ("///", "---", ".", ".."):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                sanitize_branch(branch)
        for phrase in (
            're.sub(r"[^A-Za-z0-9._-]+", "-", full_branch)',
            're.sub(r"-+", "-", value).strip("-")',
        ):
            self.assertEqual(self.protocol.count(phrase), 1)
        for phrase in (
            "preserve ASCII letter case",
            "reject the result when it is empty, `.` or `..`",
        ):
            self.assertIn(normalized(phrase), self.protocol_normalized)

    def test_materialized_fixture_resolves_and_verifies_from_foreign_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            foreign = temp / "foreign"
            foreign.mkdir()
            self.materialize_contract_repo(repo)
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            contract_root = (
                repo / ".notes" / sanitize_branch(branch) / "contract"
            )

            self.assertEqual(branch, "feature/proj-123")
            self.assertEqual(
                json.loads(
                    (contract_root / "current.json").read_text(encoding="utf-8")
                ),
                {"version": 1},
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(HELPER),
                    "verify",
                    "--root",
                    str(contract_root),
                ],
                cwd=foreign,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["version"], 1)

    def test_producer_approval_is_discovered_by_consumer_from_foreign_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            repo = temp / "repo"
            foreign = temp / "foreign"
            repo.mkdir()
            foreign.mkdir()
            subprocess.run(
                ["git", "init", "-b", "feature/proj-123"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "eval@example.com"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Skill Eval"],
                cwd=repo,
                check=True,
            )
            (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
            subprocess.run(["git", "add", "seed.txt"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "seed"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (repo / ".notes").mkdir()
            draft = temp / "contract.md"
            draft.write_text("# Contract\n\nBehavior B1\n", encoding="utf-8")
            producer_root = (
                repo / ".notes" / "feature-proj-123" / "contract"
            )

            approved = subprocess.run(
                [
                    sys.executable,
                    str(HELPER),
                    "approve",
                    "--root",
                    str(producer_root),
                    "--draft",
                    str(draft),
                    "--ticket",
                    "PROJ-123",
                    "--branch",
                    "feature/proj-123",
                    "--base-sha",
                    base_sha,
                    "--approved-by",
                    "Carlos",
                    "--approved-at",
                    "2026-07-23T12:00:00-03:00",
                ],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)

            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            consumer_root = (
                repo / ".notes" / sanitize_branch(branch) / "contract"
            )
            self.assertEqual(consumer_root, producer_root)
            self.assertEqual(
                json.loads(
                    (consumer_root / "current.json").read_text(
                        encoding="utf-8"
                    )
                ),
                {"version": 1},
            )

            verified = subprocess.run(
                [
                    sys.executable,
                    str(HELPER),
                    "verify",
                    "--root",
                    str(consumer_root),
                ],
                cwd=foreign,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)
            payload = json.loads(verified.stdout)
            self.assertTrue(payload["valid"])
            self.assertEqual(payload["version"], 1)

    def test_protocol_is_read_before_contract_path_discovery(self):
        self.assert_ordered(
            self.skill,
            "absolute directory containing this loaded `SKILL.md`",
            "Read the sibling protocol completely",
            "Sanitize the full branch",
            "Look for `current.json`",
            "scripts/contract_state.py verify",
        )

    def test_present_pointer_requires_full_identity_and_integrity_gate(self):
        for phrase in (
            "A present but malformed, incomplete, or unverifiable `current.json`",
            "never legacy fallback",
            "approval branch equals the full current branch",
            "approval ticket equals the normalized ticket",
            "approval version equals the active version",
            "git merge-base --is-ancestor <base-sha> HEAD",
        ):
            self.assertIn(normalized(phrase), self.skill_normalized)

    def test_contract_authority_drives_tdd_and_drift_boundaries(self):
        for phrase in (
            "approved contract outranks session memory, older plans",
            "Required behaviors",
            "Acceptance evidence",
            "RED → GREEN → REFACTOR",
            "Read-only tests and commands may discover and prove a deviation",
            "appends the complete `D<n>` before implementation relies",
            "stop before writing tests or source that encode the changed agreement",
            "never put a contract deviation in the ledger",
            "`/change-contract`",
        ):
            self.assertIn(normalized(phrase), self.skill_normalized)

    def test_protocol_owns_ledger_shape_and_serialization(self):
        for phrase in (
            "## D<n> — <ISO-8601 timestamp> — <agent>",
            "- Affected clauses:",
            "- Discovered fact:",
            "- Actual approach:",
            "- Reason for proceeding:",
            "- Alternatives considered:",
            "- Risk delta:",
            "- Verification evidence:",
            "strictly monotonic",
            "`file:line`",
            "command evidence",
            "parent agent is the only writer",
        ):
            self.assertIn(normalized(phrase), self.protocol_normalized)

    def test_subagents_receive_read_only_contract_context(self):
        for phrase in (
            "contract path, approved hash, ledger path, and drift rules",
            "read-only",
            "return proposed entries",
            "parent independently verifies",
            "appends serially",
        ):
            self.assertIn(normalized(phrase), self.skill_normalized)

    def test_contract_and_legacy_reports_have_separate_scopes(self):
        contract_start = self.skill.index("In contract mode, report:")
        legacy_start = self.skill.index("In legacy mode, report:")
        report_end = self.skill.index("Then stop", legacy_start)
        contract_report = self.skill[contract_start:legacy_start]
        legacy_report = self.skill[legacy_start:report_end]

        self.assertIn("Contract version", contract_report)
        self.assertIn("Ledger entry count", contract_report)
        self.assertNotIn("Contract version", legacy_report)
        self.assertNotIn("Ledger entry count", legacy_report)
        self.assertIn("Do not invent contract metadata", legacy_report)

    def test_legacy_flow_preserves_original_tdd_and_report(self):
        for phrase in (
            "When `current.json` is absent, use legacy mode",
            "do not create or request contract state",
            "Ticket and branch",
            "Behaviors implemented, with the test that pins each",
            "Files changed",
            "Suite result",
        ):
            self.assertIn(normalized(phrase), self.skill_normalized)

    def test_legacy_plan_tactics_do_not_override_existing_helper_reuse(self):
        for phrase in (
            "In legacy mode, use the settled session or written plan only for "
            "behaviors and non-goals",
            "Revalidate every implementation tactic against the lazy order",
            "Before the first RED, write one reuse decision for each "
            "implementation responsibility",
            "Name each matching candidate with a `file:line` anchor and mark "
            "it compatible or incompatible with evidence",
            "Reuse every compatible existing helper",
            "A compatible existing helper is mandatory even when the plan "
            "says local, manual, or new",
            "State these decisions in working notes or the transcript; do not "
            "create a repository file for them",
            "Do not begin RED until every responsibility has this decision",
        ):
            self.assertIn(normalized(phrase), self.skill_normalized)
        self.assert_ordered(
            self.skill,
            "Before the first RED, write one reuse decision",
            "For each behavior:",
        )

    def test_skill_is_ordered_and_compact(self):
        self.assert_ordered(
            self.skill,
            "### Step 1: Resolve the ticket and branch",
            "### Step 2: Resolve and verify contract state",
            "### Step 3: Load the authority",
            "### Step 4: Implement one behavior at a time",
            "### Step 5: Verify and report",
        )
        self.assertEqual(
            self.skill.count("### Step "),
            self.skill.count("**Complete when:**"),
        )
        self.assertLessEqual(len(self.skill.split()), 1200)


if __name__ == "__main__":
    unittest.main()
