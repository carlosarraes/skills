import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "qa-team" / "SKILL.md"
REFERENCES = ROOT / "qa-team" / "references"
EVALS = ROOT / "qa-team" / "evals" / "evals.json"

EXPECTED_REFERENCES = {
    "agent-selection.md",
    "incident-patterns.md",
    "personas.md",
    "reviewer-prompts.md",
    "synthesis-and-report.md",
}


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing frontmatter")
    return match.group(1)


class QaTeamProgressiveDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]

    def test_frontmatter_stays_at_the_task_2_contract(self):
        self.assertEqual(
            frontmatter(self.skill),
            "name: qa-team\n"
            "description: Use when the user asks for a multi-agent QA review team or comprehensive QA-team code review of a branch or diff, rather than acceptance testing.",
        )

    def test_entrypoint_is_a_compact_decision_complete_router(self):
        self.assertLessEqual(len(self.skill.splitlines()), 250)
        self.assertLessEqual(len(re.findall(r"\S+", self.body)), 2000)
        normalized = " ".join(self.body.lower().split())

        for phrase in (
            "explicit base wins",
            "origin/develop → origin/main → origin/master",
            "same selected base",
            "empty diff",
            "before reviewer dispatch",
            "at least four specialists",
            "reliability → security → performance → compatibility",
            "two distinct generalists",
            "fresh-eyes correctness/maintainability",
            "adversarial breakability",
            "one simultaneous multi-call dispatch",
            "before any result",
            "total isolation",
            "after every independent review completes",
            "qareport.md",
            "repository root",
        ):
            self.assertIn(phrase, normalized)

    def test_explicit_base_is_never_rewritten_as_a_remote(self):
        router = " ".join(self.body.lower().split())
        selection = " ".join(
            (REFERENCES / "agent-selection.md").read_text(encoding="utf-8").lower().split()
        )
        for text in (router, selection):
            self.assertIn("explicit base is used verbatim as supplied", text)
            self.assertIn("never prefix or normalize an explicit base", text)
            self.assertIn("only automatic detection probes `origin/`", text)

    def test_router_exposes_exact_ordered_scoring_and_verdicts(self):
        normalized = " ".join(self.body.lower().split())
        for phrase in (
            "any critical → critical",
            "two high or one high + two medium → high",
            "one high or three medium → medium",
            "otherwise → low",
            "critical → 🚫 blocked",
            "high → ⚠️ request changes",
            "medium → 💬 approve with nits",
            "low with no actionable findings → ✅ approve",
            "evaluate in this order",
            "copy-only findings are nonblocking",
            "do not create extra risk votes",
        ):
            self.assertIn(phrase, normalized)

        synthesis = " ".join(
            (REFERENCES / "synthesis-and-report.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        for text in (normalized, synthesis):
            for phrase in (
                "score the per-reviewer risk vector before deduplicating findings",
                "exactly one risk vote per deployed reviewer",
                "deduplicate only report rows after scoring",
                "duplicates add no votes beyond actual reviewer levels",
            ):
                self.assertIn(phrase, text)

    def test_router_exposes_the_canonical_specialist_roster_for_simulation(self):
        normalized = " ".join(self.body.lower().split())
        self.assertIn(
            "canonical specialist domains: `security`, `database`, `reliability`, `performance`, `frontend`, `compatibility`, `data-integrity`, `copy`",
            normalized,
        )
        self.assertIn("all eight plus both generalists means ten exact summary rows", normalized)

    def test_review_only_boundary_allows_exactly_one_report_write(self):
        normalized = " ".join(self.body.lower().split())
        for phrase in (
            "review-only",
            "exactly one allowed mutation",
            "write repository-root `qareport.md`",
            "never edit source",
            "never edit tests",
            "never edit config",
            "never fix code",
            "never commit",
            "never push",
            "never open or update a pr",
            "never commit the report",
        ):
            self.assertIn(phrase, normalized)

    def test_explicit_whole_run_simulation_forbids_commands_agents_and_writes(self):
        normalized = " ".join(self.body.lower().split())
        for phrase in (
            "entire run",
            "simulation only",
            "no repository commands",
            "no reviewer calls",
            "no file reads",
            "no writes",
            "no mutations",
            "normal runs",
        ):
            self.assertIn(phrase, normalized)

    def test_every_reference_is_linked_directly_and_references_do_not_chain(self):
        actual = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(actual, EXPECTED_REFERENCES)
        direct_links = set(re.findall(r"\]\(references/([^)]+\.md)\)", self.skill))
        self.assertEqual(direct_links, EXPECTED_REFERENCES)
        for path in REFERENCES.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\]\((?:\.\./)?references/[^)]+\.md\)")

    def test_router_names_each_reference_before_its_action(self):
        normalized = " ".join(self.body.lower().split())
        routes = {
            "agent-selection.md": ("before selecting the base", "before classifying"),
            "personas.md": ("before constructing specialist prompts",),
            "incident-patterns.md": ("before constructing specialist prompts",),
            "reviewer-prompts.md": ("before constructing any prompt", "before dispatch"),
            "synthesis-and-report.md": ("before convergence", "before writing"),
        }
        for filename, signals in routes.items():
            self.assertIn(filename, normalized)
            for signal in signals:
                self.assertIn(signal, normalized)

    def test_references_preserve_selection_prompt_and_report_contracts(self):
        contents = {
            path.name: " ".join(path.read_text(encoding="utf-8").lower().split())
            for path in REFERENCES.glob("*.md")
        }

        selection = contents["agent-selection.md"]
        for phrase in (
            "explicit base",
            "origin/develop",
            "origin/main",
            "origin/master",
            "--name-only",
            "full triple-dot diff",
            "commit log",
            "same selected base",
            "empty diff",
            "reliability, security, performance, compatibility",
            "at least four specialists",
            "generalist-a",
            "generalist-b",
        ):
            self.assertIn(phrase, selection)

        prompts = contents["reviewer-prompts.md"]
        for phrase in (
            "one simultaneous multi-call dispatch",
            "all selected calls",
            "before any result",
            "full diff",
            "at least 50 lines above and below",
            "only its own persona",
            "only relevant incident patterns",
            "copy receives no incident patterns",
            "fresh eyes",
            "adversarial",
            "risk level",
            "findings",
            "why it matters",
            "suggestion",
            "checklist coverage",
            "summary",
            "no issues found",
            "no other reviewer",
            "count",
            "team",
            "convergence",
        ):
            self.assertIn(phrase, prompts)

        synthesis = contents["synthesis-and-report.md"]
        for phrase in (
            "only after all reviews complete",
            "higher confidence",
            "not another risk vote",
            "copy-only",
            "any critical",
            "two high",
            "one high + two medium",
            "one high",
            "three medium",
            "approve with nits",
            "request changes",
            "blocked",
            "repository root",
            "all deployed reviewers",
            "⬜ open",
            "risk legend",
            "contributing reviewers",
            "priority",
            "brief chat handoff",
        ):
            self.assertIn(phrase, synthesis)

    def test_existing_persona_and_incident_sources_remain_complete(self):
        personas = (REFERENCES / "personas.md").read_text(encoding="utf-8")
        for codename in (
            "security",
            "database",
            "reliability",
            "compatibility",
            "data-integrity",
            "performance",
            "frontend",
            "copy",
        ):
            self.assertIn(f"`{codename}`", personas)
        incidents = (REFERENCES / "incident-patterns.md").read_text(encoding="utf-8")
        for number in range(1, 10):
            self.assertIn(f"## Pattern {number}:", incidents)

    def test_four_simulation_behavior_cases_are_tracked(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        cases = payload["evals"]
        self.assertEqual(
            [case["id"] for case in cases],
            [
                "base-precedence-empty-diff",
                "reviewer-floor-isolation",
                "ordered-risk-verdicts",
                "complete-review-only-report",
            ],
        )
        self.assertEqual(len(cases), 4)
        for case in cases:
            prompt = case["prompt"].lower()
            self.assertIn("simulation only", prompt)
            self.assertRegex(prompt, r"(?:no|do not).*(?:commands|calls|writes|mutations|files)")

    def test_automatic_base_eval_fixture_uses_remote_qualified_refs(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        prompt = next(
            case["prompt"]
            for case in payload["evals"]
            if case["id"] == "base-precedence-empty-diff"
        )

        self.assertIn(
            "origin/develop, origin/main, origin/master exist",
            prompt,
        )
        self.assertIn("origin/develop...HEAD is empty", prompt)


if __name__ == "__main__":
    unittest.main()
