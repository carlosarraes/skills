import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
FALLBACK = ROOT / "references" / "fallback-pr-body.md"
EVALS = ROOT / "evals" / "evals.json"
FACTS = ROOT / "references" / "gitflow-facts.md"
SOURCE_FACTS = ROOT.parent / "ship-gitflow" / "references" / "gitflow-facts.md"


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
            "## 5. Preview and create",
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

    def test_preview_authorizes_creation_without_a_second_confirmation(self):
        for phrase in (
            "smallest repository-defined checks",
            "exact commands and observed outcomes",
            "unrun checks remain unverified",
            "missing ui evidence pauses pr creation",
            "forge, base, title, body, verification, and missing evidence",
            "normal non-force push",
            "invocation authorizes normal non-force push and forge creation after preview",
        ):
            self.assertIn(normalized(phrase), self.flat)
        self.assertLess(
            self.flat.index("preview all of the forge, base, title, body, verification, and missing evidence"),
            self.flat.index("normal non-force push"),
        )
        for forbidden in ("explicit approval", "ask for approval", "approval checkpoint", "require approval"):
            self.assertNotIn(forbidden, self.flat)

    def test_gitflow_mode_uses_canonical_facts_and_two_leg_pipeline_lifecycle(self):
        for phrase in (
            "exact `gitflow` argument",
            "one portable pr by default",
            "[gitflow facts](references/gitflow-facts.md)",
            "Zapsign/Bitbucket Gitflow",
            "{TICKET}-prd",
            "main",
            "{TICKET}-hml",
            "homolog",
            "cherry-picked equivalent patches",
            "idempotent existing-resource reuse",
            "bt pick",
            "never merge between bases",
            "no force push",
            "two informative prs",
            "terminal pipeline monitoring",
        ):
            self.assertIn(normalized(phrase), self.flat)

    def test_gitflow_facts_are_preserved_under_opening_prs(self):
        self.assertTrue(FACTS.is_file())
        self.assertEqual(FACTS.read_text(encoding="utf-8"), SOURCE_FACTS.read_text(encoding="utf-8"))

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
            {
                "visible-frontend-change",
                "backend-data-change",
                "mixed-change-without-template",
                "dirty-worktree-stop",
                "missing-ui-evidence-stop",
                "gitflow-twin-release",
            },
        )
        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertTrue(case["expectations"])
            case_text = normalized(" ".join([case["prompt"], case["expected_output"]] + case["expectations"]))
            self.assertNotIn("approval checkpoint", case_text)
            self.assertNotIn("require approval", case_text)

        gitflow = next(case for case in payload["evals"] if case["id"] == "gitflow-twin-release")
        gitflow_text = normalized(" ".join([gitflow["prompt"], gitflow["expected_output"]] + gitflow["expectations"]))
        for phrase in (
            "exact gitflow argument",
            "{ticket}-prd from main",
            "{ticket}-hml from homolog",
            "cherry-picked equivalent patches",
            "existing-resource reuse",
            "two informative prs",
            "both pipelines",
        ):
            self.assertIn(normalized(phrase), gitflow_text)

    def test_no_template_case_can_read_and_verify_the_fallback_schema(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        case = next(case for case in payload["evals"] if case["id"] == "mixed-change-without-template")
        prompt = case["prompt"].lower()
        self.assertIn("may read only the opening-prs skill's direct fallback pr body reference", prompt)
        self.assertIn("must read that reference before answering", prompt)
        self.assertIn("use every exact section heading", prompt)
        expected = normalized(" ".join(case["expectations"]))
        for phrase in (
            "summary, customer or user value, what changed, why",
            "what reviewers need to know, test plan, checklist, and completion check",
            "architecture or flow and screenshots or recordings",
            "out of scope only when useful",
        ):
            self.assertIn(normalized(phrase), expected)

    def test_skill_is_runtime_and_forge_neutral(self):
        for forbidden in ("generated with claude", "co-authored-by: claude", "gh pr create --base develop", "mon-xxx"):
            self.assertNotIn(forbidden, self.flat)


if __name__ == "__main__":
    unittest.main()
