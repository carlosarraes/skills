import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"


def normalized(text):
    return " ".join(text.split())


class CheckContractSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.flat_skill = normalized(self.skill)

    def assert_ordered(self, *phrases):
        positions = [self.skill.find(phrase) for phrase in phrases]
        self.assertNotIn(-1, positions, phrases)
        self.assertEqual(positions, sorted(positions), phrases)

    def test_is_explicitly_invoked_and_at_most_500_words(self):
        self.assertTrue(self.skill.startswith("---\n"))
        frontmatter = self.skill.split("---", 2)[1]
        self.assertIn("name: check-contract", frontmatter)
        self.assertIn("description: Use only for explicit contract audits.", frontmatter)
        self.assertIn("disable-model-invocation: true", frontmatter)
        self.assertLessEqual(len(self.skill.split()), 500)

    def test_skill_is_thin_runtime_choreography(self):
        for phrase in (
            "scripts/check_contract.py start",
            "scripts/check_contract.py continue",
            "NeedJudgment",
            "AuditComplete",
            "AuditStopped",
            "runtime-issued evidence IDs",
            "do not inspect the target repository directly",
            "do not choose the verdict or route",
            "do not retry",
        ):
            self.assertIn(phrase, self.skill)
        self.assertNotIn("git diff ", self.skill)
        self.assertNotIn("git show ", self.skill)
        self.assertNotIn("git grep ", self.skill)

    def test_resolves_and_uses_the_installed_script_absolutely(self):
        for phrase in (
            "absolute directory containing this loaded `SKILL.md`",
            "<check-contract-skill-dir>/scripts/check_contract.py",
            "absolute script path",
        ):
            self.assertIn(phrase, self.skill)
        self.assertNotRegex(
            self.skill,
            r"(?m)^python(?:3)? scripts/check_contract\.py",
        )
        self.assertIn(
            "python <check-contract-skill-dir>/scripts/check_contract.py start\n",
            self.skill,
        )
        for broker_forbidden_option in (
            "--repo",
            "--branch",
            "--ticket",
            "--request-id",
            "--narrative",
            "--then-repo",
            "--deadline-seconds",
        ):
            self.assertNotIn(broker_forbidden_option, self.skill)

    def test_uses_one_closed_three_call_continuation_flow(self):
        self.assertEqual(
            self.skill.count(
                "python <check-contract-skill-dir>/scripts/check_contract.py start"
            ),
            1,
        )
        self.assertEqual(
            self.skill.count(
                "python <check-contract-skill-dir>/scripts/check_contract.py continue"
            ),
            2,
        )
        self.assert_ordered(
            "scripts/check_contract.py start",
            "code packet",
            "code response",
            "first `continue`",
            "reconciliation packet",
            "reconciliation response",
            "final `continue`",
            "AuditComplete",
        )

    def test_code_response_is_exact_and_evidence_bounded(self):
        for phrase in (
            "write exactly one UTF-8 JSON object",
            "`schema_version`, `session`, `nonce`, `packet_sha256`, `kind`, "
            "and `judgment`",
            "`kind` is `code`",
            "exactly the runtime-issued clause IDs",
            "exactly the runtime-issued changed-path IDs",
            "only runtime-issued evidence IDs",
            "no extra keys",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_code_response_names_the_closed_runtime_enums(self):
        for phrase in (
            "`MET | UNMET | EXCEEDED | INDETERMINATE`",
            "`UNEARNED_LOCAL | UNEARNED_MODULE | "
            "UNEARNED_RUNTIME_DEPENDENCY | UNEARNED_CONFIGURATION | "
            "UNEARNED_PUBLIC_INTERFACE | QUESTIONABLE_LOCAL | "
            "QUESTIONABLE_OTHER`",
            "`REUSED | NO_REUSE_AVAILABLE | DUPLICATED | BYPASSED | "
            "NEAR_DUPLICATE | INDETERMINATE`",
            "unique",
            "positive integer",
            "non-empty",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_fidelity_evidence_uses_runtime_map_and_reasons_stay_bounded(self):
        for phrase in (
            "For each fidelity clause, choose evidence only from "
            "`fidelity_evidence_ids[clause_id]`",
            "one short sentence per reason",
        ):
            self.assertIn(phrase, self.flat_skill)
        for duplicated_policy in (
            "behavior | public-contract | risk | acceptance",
            "source evidence is forbidden for fidelity",
        ):
            self.assertNotIn(duplicated_policy, self.flat_skill)

    def test_responder_consumes_runtime_semantics_and_chronology(self):
        for phrase in (
            "consume the packet's `semantics` and `chronology`",
            "copy their generation values into `semantic_generation` and "
            "`chronology_generation`",
            "reuse item copies the applicable issued `helper_fact_ids`",
        ):
            self.assertIn(phrase, self.flat_skill)
        self.assertNotIn("CORRECTNESS_DEFECT_IS_NOT_YAGNI", self.skill)

    def test_reconciliation_response_is_exact_and_probe_bounded(self):
        for phrase in (
            "match the packet's `response_schema` exactly",
            "`kind` is `reconciliation`",
            "select at most one runtime-issued probe ID",
            "select no probe with `null`",
            "only runtime-issued evidence IDs",
            "no extra keys",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_runtime_owns_repository_actions_and_terminal_output(self):
        for phrase in (
            "do not inspect the target repository directly",
            "do not write the report directly",
            "do not calculate aggregates",
            "do not choose the verdict or route",
            "do not retry",
            "do not invoke a recommended skill",
            "Surface every `NeedJudgment`, `AuditComplete`, or `AuditStopped` "
            "exactly as returned",
        ):
            self.assertIn(phrase, self.flat_skill)
        for forbidden in (
            "resolve-consumer",
            "contract_state.py",
            "contract-protocol.md",
            "Atomically create or replace",
            "Render the complete report",
        ):
            self.assertNotIn(forbidden, self.skill)

    def test_compound_request_uses_latest_token_in_one_logical_session(self):
        for phrase in (
            "For a compound A-then-B request",
            "the host-issued request manifest owns both targets",
            "keep one logical runtime session",
            "use the latest returned `session` for each `continue`",
            "never run a second `start` command",
        ):
            self.assertIn(phrase, self.flat_skill)
        self.assertNotIn(
            "use the returned `session` for both continuations",
            self.flat_skill,
        )

    def test_safety_boundary_is_report_only_and_immutable(self):
        for phrase in (
            "report-only",
            "The runtime may create or replace only the active "
            "`check-report.md`",
            "do not fix code",
            "do not edit the contract or ledger",
            "do not post, commit, push, or approve",
        ):
            self.assertIn(phrase, self.flat_skill)


if __name__ == "__main__":
    unittest.main()
