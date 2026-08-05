import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "chaos-engineering" / "SKILL.md"
REFERENCES = ROOT / "chaos-engineering" / "references"
EVALS = ROOT / "chaos-engineering" / "evals" / "evals.json"

EXPECTED_REFERENCES = {
    "chaos-categories.md",
    "chaos-plan.md",
    "execution.md",
    "handback.md",
    "local-discovery.md",
    "tdd-remediation.md",
}


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing frontmatter")
    return match.group(1)


class ChaosEngineeringProgressiveDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]

    def test_frontmatter_stays_at_the_task_2_contract(self):
        self.assertEqual(
            frontmatter(self.skill),
            "name: chaos-engineering\n"
            "description: Use when a locally running, feature-complete branch needs resilience, abuse, fuzz, race, dependency-failure, or adversarial testing after its happy path works.",
        )

    def test_entrypoint_is_a_compact_decision_complete_router(self):
        self.assertLessEqual(len(self.skill.splitlines()), 250)
        self.assertLessEqual(len(re.findall(r"\S+", self.body)), 2000)

        normalized = " ".join(self.body.lower().split())
        for phase in (
            "gather",
            "steady-state",
            "exactly seven",
            "single parallel batch",
            "synthesize",
            "display",
            "user selects",
            "sequentially",
            "tdd",
            "final report",
            "hand back",
        ):
            self.assertIn(phase, normalized)

        for hard_rule in (
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "authorization never waives",
            "inconclusive",
            "at most three total attempts",
            "one local commit per successful finding",
            "never push",
            "never open a pr",
            "never merge",
            "never amend",
            "never bypass hooks",
            "never use `git add .`",
            "never use `git add -a`",
        ):
            self.assertIn(hard_rule, normalized)

    def test_every_reference_is_linked_directly_and_references_do_not_chain(self):
        actual = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(actual, EXPECTED_REFERENCES)

        direct_links = set(re.findall(r"\]\(references/([^)]+\.md)\)", self.skill))
        self.assertEqual(direct_links, EXPECTED_REFERENCES)

        for path in REFERENCES.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\]\((?:\.\./)?references/[^)]+\.md\)")

    def test_router_names_the_reference_required_before_each_conditional_action(self):
        normalized = " ".join(self.body.lower().split())
        routes = {
            "local-discovery.md": ("before discovery", "health-check"),
            "chaos-categories.md": ("before defining", "before dispatch"),
            "chaos-plan.md": ("before writing", "overwrite"),
            "execution.md": ("before parsing", "before executing"),
            "tdd-remediation.md": ("before fixing", "violated"),
            "handback.md": ("before reporting", "hand-back"),
        }
        for filename, signals in routes.items():
            self.assertIn(filename, normalized)
            for signal in signals:
                self.assertIn(signal, normalized)

    def test_preview_mode_requires_an_explicit_whole_run_no_execution_request(self):
        normalized = " ".join(self.body.lower().split())
        self.assertIn("entire run", normalized)
        self.assertIn("no execution or mutation", normalized)
        self.assertIn("read-only experiments", normalized)
        self.assertIn("still execute", normalized)

        plan = " ".join(
            (REFERENCES / "chaos-plan.md").read_text(encoding="utf-8").lower().split()
        )
        self.assertIn("entire run", plan)
        self.assertIn("no execution or mutation", plan)

    def test_overall_verdict_distinguishes_mixed_resilience_from_broad_failure(self):
        normalized = " ".join(self.body.lower().split())
        self.assertIn("mixed meaningful success", normalized)
        self.assertIn("broadly unsafe", normalized)

        handback = " ".join(
            (REFERENCES / "handback.md").read_text(encoding="utf-8").lower().split()
        )
        for phrase in (
            "at least one meaningful surface is resilient or fixed",
            "material selected finding remains failed or inconclusive",
            "no meaningful resilience remains",
            "core feature is broadly unsafe",
        ):
            self.assertIn(phrase, handback)

    def test_references_preserve_load_bearing_contracts(self):
        contents = {
            path.name: " ".join(path.read_text(encoding="utf-8").lower().split())
            for path in REFERENCES.glob("*.md")
        }

        discovery = contents["local-discovery.md"]
        for phrase in (
            "linear",
            "jira",
            "case-insensitively",
            "diff is the authoritative",
            ".notes",
            "ai_docs",
            "localhost",
            "unreachable",
            "static",
        ):
            self.assertIn(phrase, discovery)

        categories = contents["chaos-categories.md"]
        for phrase in (
            "exactly seven",
            "single parallel batch",
            "independent",
            "do not mention",
            "input / injection",
            "auth / security",
            "state / race",
            "dependency",
            "resource",
            "frontend / ux",
            "time",
            "3–8",
            "500 words",
            "steady-state",
        ):
            self.assertIn(phrase, categories)

        plan = contents["chaos-plan.md"]
        for phrase in (
            ".notes/<branch-name>/chaos-plan.md",
            "ai_docs/<branch-name>/chaos-plan.md",
            "slashes",
            "explicit confirmation",
            "offer to show a diff",
            "data-mutating",
            "auth bypass",
            "destructive risk",
            "skipped",
            "simulation",
            "do not write",
        ):
            self.assertIn(phrase, plan)

        execution = contents["execution.md"]
        for phrase in (
            "all",
            "ids",
            "category",
            "abort",
            "strictly sequential",
            "status",
            "response body",
            "response time",
            "server logs",
            "db state",
            "agent-browser",
            "invalidates",
            "inconclusive",
            "simulation",
            "no experiment",
        ):
            self.assertIn(phrase, execution)

        remediation = contents["tdd-remediation.md"]
        for phrase in (
            "p0/p1",
            "p2/p3",
            "passes immediately",
            "at most three total attempts",
            "explicit path",
            "one local commit per successful finding",
            "why",
            "never `--no-verify`",
            "never `git add .`",
            "changelog.md",
            "tasks.md",
            "no test",
        ):
            self.assertIn(phrase, remediation)

        handback = contents["handback.md"]
        for phrase in (
            "every selected experiment",
            "yes / partial / no",
            "branch remains checked out",
            "never push",
            "force-push",
            "open a pr",
            "merge",
            "amend",
            "seed-data",
            "clean-up",
        ):
            self.assertIn(phrase, handback)

    def test_four_simulation_behavior_cases_are_tracked(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        cases = payload["evals"]
        self.assertEqual(
            [case["id"] for case in cases],
            [
                "nonlocal-refusal",
                "unreachable-static-plan",
                "oracle-overwrite-selection",
                "bounded-tdd-no-publish",
            ],
        )
        self.assertEqual(len(cases), 4)
        for case in cases:
            prompt = case["prompt"].lower()
            self.assertIn("simulation only", prompt)
            self.assertRegex(prompt, r"(?:no|do not).*(?:mutations|writes|edits|agents|networks)")


if __name__ == "__main__":
    unittest.main()
