import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
FALLBACK = ROOT / "references" / "fallback-pr-body.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.lower().split())


class OpeningPrsSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat = normalized(self.body)

    def test_frontmatter_is_model_invoked_and_bounded_to_pr_opening(self):
        frontmatter = self.skill.split("---", 2)[1]
        self.assertIn("name: opening-prs", frontmatter)
        self.assertNotIn("disable-model-invocation", frontmatter)
        for phrase in ("open", "create", "draft", "informative pull request", "completed branch"):
            self.assertIn(phrase, frontmatter.lower())

    def test_five_ordered_gates_have_checkable_completion_criteria(self):
        headings = (
            "## 1. Establish the target",
            "## 2. Reconstruct the change",
            "## 3. Verify the changed behavior",
            "## 4. Draft the reviewer brief",
            "## 5. Approve and create",
        )
        positions = [self.body.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.body.count("**Complete when:**"), 5)

    def test_repository_authority_and_pr_only_boundary_are_explicit(self):
        for phrase in (
            "repository instructions and canonical pull-request template win",
            "dirty worktree",
            "atomic-commit",
            "never create, amend, split, or rewrite commits",
            "one base/head range",
            "every changed file",
        ):
            self.assertIn(normalized(phrase), self.flat)

    def test_impact_table_covers_frontend_backend_data_and_operations(self):
        for phrase in (
            "visible ui",
            "screenshot or recording",
            "frontend state, routing, or data flow",
            "api or backend",
            "compatibility",
            "data, migration, or index",
            "configuration, dependency, or rollout",
        ):
            self.assertIn(normalized(phrase), self.flat)

    def test_verification_and_approval_are_evidence_bound(self):
        for phrase in (
            "smallest repository-defined checks",
            "exact commands and observed outcomes",
            "unrun checks remain unverified",
            "missing ui evidence pauses pr creation",
            "forge, base, title, body, verification, and missing evidence",
            "explicit approval",
            "normal non-force push",
        ):
            self.assertIn(normalized(phrase), self.flat)
        self.assertLess(self.flat.index("explicit approval"), self.flat.index("normal non-force push"))

    def test_fallback_is_loaded_only_when_repository_has_no_template(self):
        self.assertIn("[fallback pr body](references/fallback-pr-body.md)", self.body.lower())
        fallback = normalized(FALLBACK.read_text(encoding="utf-8"))
        for phrase in (
            "summary", "customer or user value", "what changed", "why",
            "architecture or flow", "what reviewers need to know", "test plan",
            "screenshots or recordings", "out of scope", "checklist",
            "remove every unused optional section", "no placeholders",
        ):
            self.assertIn(normalized(phrase), fallback)

    def test_behavior_cases_cover_all_branches(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "opening-prs")
        self.assertEqual(
            {case["id"] for case in payload["evals"]},
            {"visible-frontend-change", "backend-data-change", "mixed-change-without-template", "dirty-worktree-stop", "missing-ui-evidence-stop"},
        )
        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertTrue(case["expectations"])

    def test_skill_is_runtime_and_forge_neutral(self):
        for forbidden in ("generated with claude", "co-authored-by: claude", "gh pr create --base develop", "mon-xxx"):
            self.assertNotIn(forbidden, self.flat)


if __name__ == "__main__":
    unittest.main()
