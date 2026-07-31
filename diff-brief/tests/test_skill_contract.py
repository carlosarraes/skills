import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.split())


class DiffBriefSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.flat_skill = normalized(self.skill)

    def assert_ordered(self, *phrases):
        positions = [self.skill.find(phrase) for phrase in phrases]
        self.assertNotIn(-1, positions, phrases)
        self.assertEqual(positions, sorted(positions), phrases)

    def test_discovery_is_specific_and_skill_is_concise(self):
        self.assertTrue(self.skill.startswith("---\n"))
        frontmatter = self.skill.split("---", 2)[1]
        self.assertIn("name: diff-brief", frontmatter)
        for trigger in (
            "arbitrary PR",
            "branch",
            "commit",
            "range",
            "diff brief",
            "change summary",
            "risk map",
            "fast review triage",
            "someone else's change",
        ):
            self.assertIn(trigger, frontmatter)
        self.assertLessEqual(len(self.skill.split()), 500)

    def test_boundary_names_adjacent_workflows(self):
        for phrase in (
            "review triage",
            "explain-diff",
            "teaching",
            "check-contract",
            "expected-versus-actual",
            "clean-up",
            "review-swarm",
            "finding or fixing",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_resolves_and_records_an_immutable_target(self):
        for phrase in (
            "Determine the base and head",
            "repository",
            "base SHA",
            "head SHA",
            "target URL or ID",
            "verification limits",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_reverse_summary_treats_narrative_as_claims(self):
        for phrase in (
            "code as shipped",
            "surrounding code",
            "author/agent memory",
            "Description/ticket are claims",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_report_has_stable_positive_recipe(self):
        self.assert_ordered(
            "## Verdict",
            "## Behavior as shipped",
            "## Review map",
            "## Focused tour",
            "## Findings and unknowns",
            "## Verification signal",
            "## Recommended next action",
            "## Handoff",
        )
        self.assertIn("every changed file", self.flat_skill)

    def test_persisted_report_ends_with_handoff_footer(self):
        for phrase in (
            "End the persisted report with this compact footer",
            "## Handoff",
            "local report path",
            "exact optional Snapdoc publish command",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_report_recipe_enforces_compact_default_and_large_diff_grouping(self):
        for phrase in (
            "Default: 600 words or fewer",
            ">20 changed files",
            "group low-risk files by shared responsibility",
            "account for every path",
            "one evidence-dense table",
            "3-7 focused-tour and findings items total",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_labels_are_reserved_for_material_findings_and_unknowns(self):
        for phrase in (
            "Label only material findings/unknowns",
            "Grounded summary sentences need citations, not labels",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_merged_pr_identity_preserves_review_and_shipped_snapshots(self):
        for phrase in (
            "For a merged PR",
            "original PR base/head range as the review target",
            "shipped/squash commit separately when different",
            "cite the snapshot actually inspected",
            "For other targets: one immutable base/head pair",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_risk_levels_and_semantics_are_explicit(self):
        for phrase in (
            "`SAFE | LOW | MEDIUM | HIGH`",
            "auth",
            "tenant",
            "billing",
            "migrations",
            "data loss",
            "concurrency",
            "public API",
            "irreversible",
            "`UNCLEAR` finding",
            "cannot be SAFE or LOW",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_risk_is_consequence_not_review_priority(self):
        for phrase in (
            "Risk = consequence/blast radius; review priority is separate",
            "non-executable docs or test-only changes",
            "cannot alter build/release/runtime artifacts",
            "Changed tests may affect verification outcomes but remain SAFE "
            "consequence risk",
            "A weak test can be SAFE file risk yet high review priority",
            "`Config/scripts/CI`: never SAFE merely for being non-production",
        ):
            self.assertIn(phrase, self.flat_skill)
        self.assertNotIn(
            "no build, CI, release, fixture, snapshot, or operational effect",
            self.flat_skill,
        )

    def test_evidence_and_human_reading_budget_are_bounded(self):
        for phrase in (
            "forge permalink",
            "`file:line`",
            "`Fact`",
            "`Inference`",
            "`Unknown`",
            "No claim without evidence",
            "load-bearing hunks",
            "reading order",
        ):
            self.assertIn(phrase, self.flat_skill)
        self.assertIn("Do not dump the diff", self.skill)

    def test_audit_dimensions_require_positive_clean_evidence(self):
        for phrase in (
            "existing helpers",
            "duplicate implementation",
            "tests against risky behavior",
            "API shape",
            "scope",
            "over-defensiveness",
            "performance",
            "maintainability",
            "YAGNI",
            "`NO ISSUE` with evidence",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_clean_dimensions_collapse_into_one_evidence_dense_line(self):
        for phrase in (
            "Clean dimensions: one compact line",
            "`Checks: NO ISSUE",
            "repository-level helper/reuse search evidence",
            "Expand concern/unknown dimensions only",
            "omit irrelevant high-risk domains",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_reuse_no_issue_records_reproducible_search_provenance(self):
        for phrase in (
            "Reuse `NO ISSUE`: compact search provenance",
            "scope, symbols/patterns, closest candidate inspected",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_low_and_medium_risk_have_distinct_consequence_semantics(self):
        for phrase in (
            "`LOW`: localized/reversible, limited consumers, outside sensitive "
            "boundaries",
            "`MEDIUM`: shared runtime/operational behavior or cross-module/caller "
            "blast radius",
            "bounded/reversible; not `HIGH`",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_one_fresh_context_verification_pass_is_required_when_available(self):
        for phrase in (
            "With subagents, dispatch one fresh-context read-only auditor",
            "immutable target/diff plus draft",
            "not author memory",
            "shipped behavior",
            "reuse/closest existing candidate",
            "risky tests",
            "higher-level decision gaps",
            "evidence-only corrections/unknowns",
            "main agent reconciles the final brief",
            "one verification pass",
            "not review-swarm/personas/posting/fixing",
            "`Fresh-context pass: unavailable` as `Unknown`",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_tracked_behavioral_evals_have_required_schema_and_discriminators(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "diff-brief")
        evals = payload["evals"]
        self.assertEqual(len(evals), 3)
        ids = [case["id"] for case in evals]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {"pr1414", "low-risk", "architecture"})

        discriminators = (
            "every changed file",
            "risk",
            "reuse provenance",
            "fresh-context pass",
            "evidence",
            "verdict",
            "600 words",
            "handoff",
            "verification evidence",
        )
        for case in evals:
            self.assertIsInstance(case["prompt"], str)
            self.assertTrue(case["prompt"].strip())
            expectations = case["expectations"]
            self.assertIsInstance(expectations, list)
            self.assertTrue(expectations)
            joined = " ".join(expectations).lower()
            for discriminator in discriminators:
                self.assertIn(discriminator, joined, case["id"])
            self.assertNotIn("assertions", case)

    def test_executed_checks_preserve_replayable_verification_evidence(self):
        for phrase in (
            "`<report-stem>.verification.txt`",
            "immutable snapshot",
            "exact command",
            "exit status",
            "concise raw/result summary",
            "`Verification signal` cites its local path",
            "No preserved evidence",
            "check claim is `Unknown`/unverified, not proof",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_is_report_only_and_external_actions_need_permission(self):
        for phrase in (
            "read-only and report-only",
            "Do not modify code",
            "post PR comments",
            "publish externally",
            "explicit user request",
        ):
            self.assertIn(phrase, self.flat_skill)

    def test_artifact_contract_gates_snapdoc_and_video(self):
        for phrase in (
            "Always save the Markdown report locally",
            "ignored output location",
            "Mermaid only when it materially clarifies at least three",
            "snapdoc publish <report>.md --markdown --title",
            "stable URL",
            "local path",
            "exact optional Snapdoc publish command",
            "Video belongs to `qa-pr`",
        ):
            self.assertIn(phrase, self.flat_skill)


if __name__ == "__main__":
    unittest.main()
