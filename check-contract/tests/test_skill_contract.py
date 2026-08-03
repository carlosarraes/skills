import re
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
            "Runtime owns repository inspection",
            "Do none",
            "do not retry/invoke a recommended skill",
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
            "Evaluate fidelity against the exact contract noun phrases",
            "Independent-axis failures do not broaden those noun phrases or "
            "imply fidelity failure",
            "`fidelity_evidence_ids[clause_id]`; omit all others",
            "one short sentence per reason",
        ):
            self.assertIn(phrase, self.flat_skill)
        for duplicated_policy in (
            "behavior | public-contract | risk | acceptance",
            "source evidence is forbidden for fidelity",
        ):
            self.assertNotIn(duplicated_policy, self.flat_skill)

    def test_grouped_explicit_cases_still_demonstrate_mapped_behavior(self):
        self.assertIn(
            "Explicit assertions/`subTest` cases directly proving mapped behavior "
            "remain demonstrative when grouped",
            self.flat_skill,
        )

    def test_responder_consumes_runtime_semantics_and_chronology(self):
        for phrase in (
            "consume packet `semantics.generation` into `semantic_generation`",
            "packet `chronology.generation` into `chronology_generation`",
            "Every reuse item has `helper_fact_ids`: applicable issued IDs or `[]`",
        ):
            self.assertIn(phrase, self.flat_skill)
        self.assertNotIn("CORRECTNESS_DEFECT_IS_NOT_YAGNI", self.skill)

    def test_yagni_and_reuse_follow_issued_chronology_and_search(self):
        for phrase in (
            "`INTRODUCED_BEFORE_AFFECTED_IMPLEMENTATION` marks a used helper "
            "earned for the affected change, not YAGNI",
            "Never strengthen issued `INDETERMINATE` chronology",
            "`R`, `S`, or `K` failure alone does not create YAGNI",
            "Give every changed-path responsibility a reuse verdict",
            "every path's `reuse_items` is nonempty",
            "Every reuse item has `helper_fact_ids`: applicable issued IDs or `[]`",
            "use `NO_REUSE_AVAILABLE` when issued full-HEAD search proves none",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_dispensable_wrapper_can_be_unearned_without_a_k_cap_failure(self):
        for phrase in (
            "Implementation-introduced or used does not itself prove earned",
            "a code-proven dispensable wrapper can be `UNEARNED_LOCAL`",
            "without a `K`-cap failure",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_current_compatible_helper_is_duplicate_without_known_chronology(self):
        self.assertIn(
            "Code-proven exact current-helper compatibility is `DUPLICATED` "
            "despite `INDETERMINATE` chronology",
            self.flat_skill,
        )
        self.assertIn(
            "Never strengthen issued `INDETERMINATE` chronology",
            self.flat_skill,
        )

    def test_code_response_collections_have_unambiguous_json_shapes(self):
        for phrase in (
            "`clauses`: JSON object keyed by exactly the runtime-issued clause IDs",
            "`path_assessments`: JSON object keyed by exactly the runtime-issued "
            "changed-path IDs",
            "`deviations`: JSON array",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_code_judgment_declares_all_five_keys_in_exact_order_and_sources(self):
        declaration = re.search(
            r"`judgment`: exactly five keys, in order: ([^.]+)\.",
            self.flat_skill,
        )
        self.assertIsNotNone(declaration)
        self.assertEqual(
            re.findall(r"`([^`]+)`", declaration.group(1)),
            [
                "semantic_generation",
                "chronology_generation",
                "clauses",
                "path_assessments",
                "deviations",
            ],
        )
        self.assertIn(
            "consume packet `semantics.generation` into `semantic_generation` "
            "and packet `chronology.generation` into `chronology_generation`",
            self.flat_skill,
        )
        self.assertNotIn(
            "`code response` `judgment`: `clauses`, `path_assessments`, "
            "`deviations`.",
            self.flat_skill,
        )

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
            "Runtime owns repository inspection/report writing/aggregate "
            "calculation/findings/verdict/route",
            "Do none; do not retry/invoke a recommended skill",
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

    def test_terminal_result_stops_all_audit_and_tool_work(self):
        for phrase in (
            "`AuditComplete` and `AuditStopped` are terminal",
            "no more tools/report reads",
            "return the exact canonical JSON",
            "exit immediately",
        ):
            self.assertIn(phrase, self.flat_skill)
        self.assertNotIn("summary artifact", self.flat_skill)
        positions = [
            self.flat_skill.find(phrase)
            for phrase in (
                "A compound transition may return the next target's `NeedJudgment`",
                "`AuditComplete` and `AuditStopped` are terminal",
                "exit immediately",
            )
        ]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))

    def test_terminal_json_has_no_markdown_wrapper_or_prose(self):
        self.assertIn(
            "return the exact canonical JSON without Markdown fences or prose",
            self.flat_skill,
        )

    def test_terminal_json_has_positive_plain_text_lexical_contract(self):
        for phrase in (
            "Return plain text",
            "copy the terminal tool result byte-for-byte",
            "first/last characters `{`/`}`",
            "nothing before/after",
            "then stop",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_error_marked_audit_stopped_is_terminal_and_unrecoverable(self):
        terminal_start = self.flat_skill.find(
            "`AuditComplete` and `AuditStopped` are terminal"
        )
        terminal_end = self.flat_skill.find("Runtime owns", terminal_start)
        self.assertGreaterEqual(terminal_start, 0)
        self.assertGreater(terminal_end, terminal_start)
        terminal_section = self.flat_skill[terminal_start:terminal_end]
        for phrase in (
            "Nonzero/error-marked tool-result `AuditStopped`",
            "terminal, not recoverable",
            "`ReportFindings` and all subsequent tools forbidden",
        ):
            self.assertIn(phrase, terminal_section)

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
            "Report-only",
            "Runtime may create/replace only active `check-report.md`",
            "do not fix code or edit contract/ledger",
            "do not post/commit/push/approve",
        ):
            self.assertIn(phrase, self.flat_skill)


if __name__ == "__main__":
    unittest.main()
