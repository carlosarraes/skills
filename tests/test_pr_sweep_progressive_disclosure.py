import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "pr-sweep" / "SKILL.md"
REFERENCES = ROOT / "pr-sweep" / "references"
EVALS = ROOT / "pr-sweep" / "evals" / "evals.json"

EXPECTED_REFERENCES = {
    "cadence.md",
    "collection-and-matrix.md",
    "conflict-resolution.md",
    "fix-protocol.md",
    "size-gate.md",
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
            "explicit list",
            "authored-pr default",
            "authority",
            "l1",
            "l2",
            "l3",
            "latest run per check name",
            "latest verdict per reviewer",
            "quiet",
            "approval",
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

    def test_selected_needs_fix_prs_dispatch_without_approval_gate(self):
        normalized = " ".join(self.body.lower().split())

        for required in (
            "dispatch every selected `needs fix` pr immediately",
            "approval state is recorded for reporting and reviewer re-request only",
            "never for permission or routing",
            "one fix agent per pr per cycle",
            "one commit push per pr per cycle",
            "approval is invalidated",
        ):
            self.assertIn(required, normalized)

        for forbidden in (
            "approval-triage",
            "approval-risk",
            "avoidable",
            "batched",
            "re-confirm",
        ):
            self.assertNotIn(forbidden, normalized)

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
            "fix-protocol.md": ("before dispatch", "needs fix"),
            "size-gate.md": ("size gate", "before"),
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
            "every collected finding",
            "exactly one terminal action",
        ):
            self.assertIn(phrase, collection)

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
            "already-resolved thread",
            "additional code",
            "title edits",
            "preserve reviews",
        ):
            self.assertIn(phrase, fix)

        size = contents["size-gate.md"]
        for phrase in (
            "idempotent",
            "effective loc",
            "size/override",
            "2,000",
            "split",
            "never infer",
            "unrelated check results",
            "status summaries",
        ):
            self.assertIn(phrase, size)

        conflict = contents["conflict-resolution.md"]
        for phrase in (
            "git status",
            "both sides",
            "history",
            "stop",
            "user work",
            "--force-with-lease",
            "format-only",
            "cherry-pick",
        ):
            self.assertIn(phrase, conflict)

        convergence = contents["review-convergence.md"]
        for phrase in ("later cycle", "new head", "green", "blocking reviewer", "handoff"):
            self.assertIn(phrase, convergence)

        cadence = contents["cadence.md"]
        for phrase in (
            "every nonterminal cycle",
            "before",
            "report",
            "waiting",
            "all selected prs are done",
            "5 minutes",
            "20 minutes",
            "cache",
            "time-sensitive",
            "validate",
        ):
            self.assertIn(phrase, cadence)

    def test_six_read_only_behavior_cases_are_tracked(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        cases = payload["evals"]
        self.assertEqual(
            [case["id"] for case in cases],
            [
                "quiet-latest-state",
                "approved-bot-fix-autonomous",
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

        size_prompt = next(case["prompt"].lower() for case in cases if case["id"] == "size-policy")
        self.assertIn("#402's latest labeled-event size-check result has not been fetched and is unknown", size_prompt)
        self.assertIn("unrelated checks are green", size_prompt)


if __name__ == "__main__":
    unittest.main()
