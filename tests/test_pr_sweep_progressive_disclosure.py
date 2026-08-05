import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "pr-sweep" / "SKILL.md"
REFERENCES = ROOT / "pr-sweep" / "references"
EVALS = ROOT / "pr-sweep" / "evals" / "evals.json"

EXPECTED_REFERENCES = {
    "approval-triage.md",
    "cadence.md",
    "collection-and-matrix.md",
    "conflict-resolution.md",
    "fix-protocol.md",
    "acme-size-gate.md",
    "review-convergence.md",
}


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing frontmatter")
    return match.group(1)


class PrSweepProgressiveDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]

    def test_frontmatter_stays_at_the_task_2_contract(self):
        self.assertEqual(
            frontmatter(self.skill),
            "name: pr-sweep\n"
            "description: Use when open non-draft PRs need ongoing convergence to mergeability across CI, conflicts, size gates, bot feedback, and human review.",
        )

    def test_entrypoint_is_a_compact_decision_complete_router(self):
        self.assertLessEqual(len(self.skill.splitlines()), 250)
        self.assertLessEqual(len(re.findall(r"\S+", self.body)), 2000)

        normalized = " ".join(self.body.lower().split())
        for required in (
            "done",
            "waiting",
            "needs fix",
            "l1",
            "l2",
            "l3",
            "latest run per check name",
            "latest verdict per reviewer",
            "quiet",
            "approval",
            "avoidable",
            "batched",
            "per pr",
            "one fix agent",
            "one commit push",
            "autonomous",
            "re-arm",
            "all selected prs",
        ):
            self.assertIn(required, normalized)

        for hard_rule in (
            "never push to a base branch",
            "never bypass hooks",
            "never dismiss",
            "never overwrite",
            "never plain `--force`",
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

    def test_router_routes_each_conditional_branch_before_action(self):
        normalized = " ".join(self.body.lower().split())
        routes = {
            "collection-and-matrix.md": ("before collecting", "classifying"),
            "approval-triage.md": ("approved", "avoidable"),
            "fix-protocol.md": ("before dispatch", "needs fix"),
            "acme-size-gate.md": ("size gate", "before"),
            "conflict-resolution.md": ("conflict", "before"),
            "review-convergence.md": ("later cycle", "green"),
            "cadence.md": ("before scheduling", "wakeup"),
        }
        for filename, signals in routes.items():
            self.assertIn(filename, normalized)
            for signal in signals:
                self.assertIn(signal, normalized)

    def test_references_preserve_load_bearing_contracts(self):
        contents = {
            path.name: " ".join(path.read_text(encoding="utf-8").lower().split())
            for path in REFERENCES.glob("*.md")
        }

        collection = contents["collection-and-matrix.md"]
        for phrase in (
            "latest run per check name",
            "latest verdict per reviewer",
            "databaseid",
            "review thread id",
            "summary-only",
            "never reply",
            "terminal-good",
            "pr url",
        ):
            self.assertIn(phrase, collection)

        approval = contents["approval-triage.md"]
        for phrase in ("one batched", "per pr", "avoidable", "merge-required", "re-confirm"):
            self.assertIn(phrase, approval)

        fix = contents["fix-protocol.md"]
        for phrase in (
            "one fix agent",
            "one commit push",
            "regression test",
            "flake",
            "reply",
            "resolve",
            "follow-up",
            "never bypass hooks",
        ):
            self.assertIn(phrase, fix)

        size = contents["acme-size-gate.md"]
        for phrase in ("idempotent", "effective loc", "size/override", "2,000", "split"):
            self.assertIn(phrase, size)

        conflict = contents["conflict-resolution.md"]
        for phrase in ("git status", "both sides", "history", "stop", "user work", "--force-with-lease"):
            self.assertIn(phrase, conflict)

        convergence = contents["review-convergence.md"]
        for phrase in ("later cycle", "new head", "green", "blocking reviewer", "handoff"):
            self.assertIn(phrase, convergence)

        cadence = contents["cadence.md"]
        for phrase in ("every nonterminal cycle", "before", "report", "waiting", "all selected prs are done"):
            self.assertIn(phrase, cadence)

    def test_six_read_only_behavior_cases_are_tracked(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        cases = payload["evals"]
        self.assertEqual(
            [case["id"] for case in cases],
            [
                "quiet-latest-state",
                "approval-gate-per-pr",
                "feedback-dedup-and-replies",
                "size-policy",
                "conflict-stop-safety",
                "delayed-convergence",
            ],
        )
        self.assertEqual(len(cases), 6)
        for case in cases:
            prompt = case["prompt"].lower()
            self.assertIn("simulation only", prompt)
            self.assertRegex(prompt, r"(?:no|do not).*(?:external|call github|modify git|real label)")


if __name__ == "__main__":
    unittest.main()
