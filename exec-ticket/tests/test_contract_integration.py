import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL = ROOT.parent / "change-contract" / "references" / "contract-protocol.md"


class ContractIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.protocol = PROTOCOL.read_text(encoding="utf-8")

    def assert_ordered(self, text, *phrases):
        positions = [text.index(phrase) for phrase in phrases]
        self.assertEqual(positions, sorted(positions), phrases)

    def test_contract_gate_follows_identity_and_precedes_implementation_writes(self):
        self.assert_ordered(
            self.skill,
            "### Step 1: Resolve the ticket and branch",
            "### Step 2: Gate on contract state before implementation writes",
            "### Step 3: Load the implementation authority",
            "### Step 4: Build one required behavior at a time",
        )
        self.assertIn(
            "before any source, test, contract, or ledger write",
            self.skill,
        )
        self.assertEqual(
            self.skill.count("### Step "),
            self.skill.count("**Complete when:**"),
        )

    def test_present_current_requires_protocol_and_helper_verification(self):
        for phrase in (
            "If `current.json` exists, read the full shared protocol",
            "scripts/contract_state.py verify",
            "A present but malformed, incomplete, or unverifiable `current.json`",
            "hard stop",
            "never fall back to the legacy flow",
        ):
            self.assertIn(phrase, self.skill)
        self.assert_ordered(
            self.skill,
            "If `current.json` exists, read the full shared protocol",
            "scripts/contract_state.py verify",
            "Only after every check passes",
        )

    def test_verified_identity_and_base_ancestry_are_required(self):
        for phrase in (
            "active version in `current.json`",
            "approval branch exactly matches the full current branch",
            "approval ticket exactly matches the normalized ticket",
            "approval version matches the active version",
            "git merge-base --is-ancestor <base-sha> HEAD",
            "approved base SHA is an ancestor of `HEAD`",
        ):
            self.assertIn(phrase, self.skill)

    def test_approved_contract_drives_tdd_and_outranks_prior_context(self):
        for phrase in (
            "approved contract outranks session memory",
            "older plans",
            "user pressure",
            "Required behaviors",
            "Acceptance evidence",
            "RED → GREEN → REFACTOR",
        ):
            self.assertIn(phrase, self.skill)
        self.assert_ordered(
            self.skill,
            "Required behaviors",
            "RED → GREEN → REFACTOR",
        )

    def test_protocol_defines_the_canonical_parent_owned_ledger(self):
        for phrase in (
            "## Execution ledger",
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
            "append before reliance",
            "parent agent is the only writer",
        ):
            self.assertIn(phrase, self.protocol)

    def test_drift_classes_have_distinct_write_boundaries(self):
        for phrase in (
            "Implementation details need no ledger entry",
            "complete proposed ledger entry",
            "independently verify its cited facts and evidence",
            "parent appends the complete next `D<n>`",
            "before the affected path is used",
            "Contract deviations are a hard stop",
            "before any affected source, test, or ledger write",
            "never append a contract deviation",
            "`/change-contract`",
        ):
            self.assertIn(phrase, self.skill)

    def test_subagents_are_read_only_contract_workers(self):
        for phrase in (
            "contract path, approved hash, ledger path, and drift rules",
            "read-only",
            "return proposed ledger entries",
            "Only the parent appends",
            "serially",
        ):
            self.assertIn(phrase, self.skill)

    def test_legacy_flow_and_reports_remain_explicit(self):
        for phrase in (
            "If `current.json` does not exist, use the legacy flow",
            "do not request, fabricate, or create contract state",
            "Ticket and branch",
            "Behaviors implemented, with the test that pins each",
            "Files changed",
            "Suite result",
            "Contract version",
            "Ledger entry count",
        ):
            self.assertIn(phrase, self.skill)
        self.assertIn(
            "Do not invent contract metadata in the legacy report",
            self.skill,
        )

    def test_sibling_contract_tools_are_resolved_independently_of_cwd(self):
        for phrase in (
            "absolute directory containing this loaded `SKILL.md`",
            "`<exec-ticket-skill-dir>/../change-contract`",
            "independent of the consumer repository working directory",
        ):
            self.assertIn(phrase, self.skill)


if __name__ == "__main__":
    unittest.main()
