import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "qa-ticket" / "SKILL.md"
REFERENCES = ROOT / "qa-ticket" / "references"
EVALS = ROOT / "qa-ticket" / "evals" / "evals.json"

EXPECTED_REFERENCES = {
    "backend-qa.md",
    "fix-retry-and-report.md",
    "frontend-qa.md",
    "qa-context.md",
    "test-plan.md",
}


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing frontmatter")
    return match.group(1)


class QaTicketProgressiveDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]

    def test_frontmatter_stays_at_the_task_2_contract(self):
        self.assertEqual(
            frontmatter(self.skill),
            "name: qa-ticket\n"
            "description: Use when the current ticket branch needs executable acceptance or smoke testing against a local backend or frontend, including fix-and-retry.",
        )

    def test_entrypoint_is_a_compact_decision_complete_router(self):
        self.assertLessEqual(len(self.skill.splitlines()), 250)
        self.assertLessEqual(len(re.findall(r"\S+", self.body)), 2000)

        normalized = " ".join(self.body.lower().split())
        for phase in (
            "preflight",
            "ticket",
            "develop...head",
            "diff-only",
            "print the complete plan",
            "before any functional test",
            "happy",
            "error",
            "edge",
            "backend",
            "frontend",
            "diagnose",
            "at most three total attempts per test",
            "final report",
        ):
            self.assertIn(phase, normalized)

        for evidence_rule in (
            "status and expected response content",
            "fresh post-action",
            "skip/inconclusive",
            "never pass",
            "every planned test",
            "every changed file",
            "acceptance criteria",
        ):
            self.assertIn(evidence_rule, normalized)

    def test_every_reference_is_linked_directly_and_references_do_not_chain(self):
        actual = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(actual, EXPECTED_REFERENCES)

        direct_links = set(re.findall(r"\]\(references/([^)]+\.md)\)", self.skill))
        self.assertEqual(direct_links, EXPECTED_REFERENCES)

        for path in REFERENCES.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\]\((?:\.\./)?references/[^)]+\.md\)")

    def test_router_names_the_reference_required_before_each_action(self):
        normalized = " ".join(self.body.lower().split())
        routes = {
            "qa-context.md": ("before preflight", "before gathering"),
            "test-plan.md": ("before drafting", "before printing"),
            "backend-qa.md": ("before any backend",),
            "frontend-qa.md": ("before any frontend",),
            "fix-retry-and-report.md": ("before diagnosing", "before the final report"),
        }
        for filename, signals in routes.items():
            self.assertIn(filename, normalized)
            for signal in signals:
                self.assertIn(signal, normalized)

    def test_explicit_whole_run_simulation_forbids_commands_and_mutations(self):
        normalized = " ".join(self.body.lower().split())
        for phrase in (
            "entire run",
            "simulation only",
            "no repository commands",
            "no provider commands",
            "no service commands",
            "no browser commands",
            "no mutations",
            "normal runs",
        ):
            self.assertIn(phrase, normalized)

    def test_frontend_edit_retry_transition_is_indivisible_and_ledgered(self):
        router = " ".join(self.body.lower().split())
        retry = " ".join(
            (REFERENCES / "fix-retry-and-report.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        frontend = " ".join(
            (REFERENCES / "frontend-qa.md").read_text(encoding="utf-8").lower().split()
        )
        transition = "frontend edit → hmr wait → network-idle wait → fresh refs → retry"
        self.assertIn(transition, router)
        self.assertIn(transition, retry)
        self.assertIn(transition, frontend)
        self.assertIn(
            "record each edit, both waits, fresh-ref acquisition, and retry in that order",
            retry,
        )
        for text in (router, retry):
            for phrase in (
                "audit every frontend edit ledger entry before retry and before reporting",
                "edit: <file> | hmr: observed | network idle: observed | fresh refs: acquired | next attempt: <n>",
                "one complete ledger row per frontend edit",
                "incomplete and invalid trace",
                "corrected before retry or report",
            ):
                self.assertIn(phrase, text)

    def test_router_keeps_exact_coverage_floor_when_references_are_not_read(self):
        normalized = " ".join(self.body.lower().split())
        for phrase in (
            "create → read → update → list → delete → verify delete",
            "document a changed rate limit but do not stress-hit it merely to prove the annotation",
            "category is exactly `happy-path`, `error`, or `edge-case`",
        ):
            self.assertIn(phrase, normalized)

    def test_references_preserve_load_bearing_contracts(self):
        contents = {
            path.name: " ".join(path.read_text(encoding="utf-8").lower().split())
            for path in REFERENCES.glob("*.md")
        }

        context = contents["qa-context.md"]
        for phrase in (
            "claude.md",
            "readme",
            "docker-compose",
            "package.json",
            "makefile",
            "health",
            "linear",
            "jira",
            "case-insensitive",
            "uppercase",
            "develop...head",
            "diff-only",
            "no changes found relative to develop",
        ):
            self.assertIn(phrase, context)

        plan = contents["test-plan.md"]
        for phrase in (
            "ticket plus diff",
            "id",
            "surface",
            "category",
            "steps",
            "expected result",
            "every changed endpoint",
            "create → read → update → list → delete → verify delete",
            "both sides",
            "permission",
            "not found",
            "conflict",
            "rate limit",
            "special characters",
            "multiple items",
            "keyboard",
            "state transitions",
            "unchanged",
            "print",
        ):
            self.assertIn(phrase, plan)

        backend = contents["backend-qa.md"]
        for phrase in (
            "openapi",
            "source route",
            "never guess",
            "curl -s -w",
            "-x post",
            "-x patch",
            "-x delete",
            "content-type: application/json",
            "body separately",
            "status and expected response content",
            "unique",
            "capture",
            "cleanup",
            "verify delete",
        ):
            self.assertIn(phrase, backend)

        frontend = contents["frontend-qa.md"]
        for phrase in (
            "agent-browser",
            "authentication",
            "router",
            "never guess",
            "snapshot",
            "current refs",
            "networkidle",
            "re-snapshot",
            "fresh post-action",
            "radix",
            "ordinary click",
        ):
            self.assertIn(phrase, frontend)

        retry = contents["fix-retry-and-report.md"]
        for phrase in (
            "test bug",
            "code bug",
            "environment",
            "at most three total attempts per test",
            "minimal",
            "changed scope",
            "hmr",
            "network idle",
            "every planned test",
            "every attempt",
            "every changed file",
            "recovery next step",
            "acceptance criteria",
        ):
            self.assertIn(phrase, retry)

    def test_four_simulation_behavior_cases_are_tracked(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        cases = payload["evals"]
        self.assertEqual(
            [case["id"] for case in cases],
            [
                "degraded-local-preflight",
                "targeted-coverage-floor",
                "evidence-not-intention",
                "bounded-retry-complete-report",
            ],
        )
        self.assertEqual(len(cases), 4)
        for case in cases:
            prompt = case["prompt"].lower()
            self.assertIn("simulation only", prompt)
            self.assertRegex(prompt, r"(?:no|do not).*(?:calls|commands|mutations|edits|services)")


if __name__ == "__main__":
    unittest.main()
