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

        retry = " ".join(
            (REFERENCES / "fix-retry-and-report.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        for text in (normalized, retry):
            for phrase in (
                "simulation ledger: `edit: <file> | hmr: would wait | network idle: would wait | fresh refs: would acquire | next attempt: <n>`",
                "classify supplied outcomes separately",
                "never claim a simulated wait, ref acquisition, edit, or retry was observed or occurred",
            ):
                self.assertIn(phrase, text)

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

    def test_missing_fixtures_use_the_combined_check_data_default(self):
        sources = [
            self.body,
            (REFERENCES / "qa-context.md").read_text(encoding="utf-8"),
            (REFERENCES / "test-plan.md").read_text(encoding="utf-8"),
        ]
        for source in sources:
            normalized = " ".join(source.lower().split())
            self.assertIn("/check-data", normalized)

        router = " ".join(self.body.lower().split())
        for phrase in (
            "fixture setup",
            "fixture setup: /check-data (default: plan → seed → verify)",
            "fixture setup: not needed — <evidence>",
            "single /check-data invocation owns all three phases",
            "never express them as multiple skills or commands",
        ):
            self.assertIn(phrase, router)

    def test_fixture_setup_line_is_exact_in_plan_and_final_report(self):
        plan_start = self.body.index("### Complete targeted plan before execution")
        plan_end = self.body.index("### Evidence, not intention", plan_start)
        report_start = self.body.index("### Complete report and truthful verdict")
        report_end = self.body.index("## Never rules", report_start)
        artifacts = (
            " ".join(self.body[plan_start:plan_end].lower().split()),
            " ".join(self.body[report_start:report_end].lower().split()),
        )
        for artifact in artifacts:
            self.assertIn(
                "fixture setup: /check-data (default: plan → seed → verify)",
                artifact,
            )
            self.assertIn("fixture setup: not needed — <evidence>", artifact)
            self.assertIn("only with evidence", artifact)

    def test_pre_output_audit_covers_both_artifacts_simulation_and_deleted_entrypoint(self):
        audit_start = self.body.index("### Pre-output audit")
        audit_end = self.body.index("## Never rules", audit_start)
        audit = " ".join(self.body[audit_start:audit_end].lower().split())
        for phrase in (
            "before returning",
            "including simulation",
            "both artifacts",
            "printed plan and final report",
            "fixture setup field",
            "rewrite any `/seed-data` occurrence",
            "entrypoint is deleted",
        ):
            self.assertIn(phrase, audit)

    def test_unavailable_surfaces_keep_the_complete_coverage_floor(self):
        sources = [
            self.body,
            (REFERENCES / "test-plan.md").read_text(encoding="utf-8"),
        ]
        for source in sources:
            normalized = " ".join(source.lower().split())
            self.assertIn(
                "complete backend and frontend happy-path/error/edge-case coverage floor",
                normalized,
            )
            self.assertIn("surface is unavailable", normalized)
            self.assertIn("mark each such result as `skip/inconclusive`", normalized)

    def test_missing_ticket_context_stays_diff_only_without_a_question_loop(self):
        sources = [
            self.body,
            (REFERENCES / "qa-context.md").read_text(encoding="utf-8"),
        ]
        normalized = " ".join(" ".join(sources).lower().split())
        for phrase in (
            "missing ticket context",
            "diff-only",
            "skip/inconclusive",
            "without prompting",
        ):
            self.assertIn(phrase, normalized)

        for forbidden in (
            "ask for the ticket id",
            "ask the user for the ticket id",
            "what's the ticket id",
        ):
            self.assertNotIn(forbidden, normalized)

    def test_degraded_preflight_prompt_is_neutral_while_rubric_keeps_behavior(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        case = next(
            case
            for case in payload["evals"]
            if case["id"] == "degraded-local-preflight"
        )
        prompt = case["prompt"].lower()
        for phrase in (
            "branch feature/catalog-filter has no ticket pattern",
            "default linear cli fails",
            "docs/config expose backend http://localhost:8000 and frontend http://127.0.0.1:3000 with auth bypass",
            "backend health is 503",
            "frontend health is 200",
            "develop...head changes a backend filter endpoint and frontend filter component",
            "acceptance text and local fixtures are unavailable",
            "user asks for a green-looking report",
            "infer backend from code and just test ui",
            "what handling follows?",
        ):
            self.assertIn(phrase, prompt)

        self.assertTrue(prompt.endswith("what handling follows?"))
        for forbidden in (
            "diff-only",
            "without asking for a ticket id",
            "/check-data",
            "/seed-data",
            "plan, seed, and verify",
            "skip/inconclusive",
            "complete plan",
            "happy/error/edge",
            "full coverage",
            "coverage",
            "verdict",
            "ordered qa action trace",
            "truthful final report",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_seed_data_mentions_are_prohibition_only_in_runtime_docs(self):
        runtime_docs = [SKILL, *sorted(REFERENCES.glob("*.md"))]
        occurrences = []
        for path in runtime_docs:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                normalized_line = " ".join(line.lower().split())
                if "/seed-data" not in normalized_line:
                    continue
                occurrences.append((path, line_number, normalized_line))
                self.assertRegex(
                    normalized_line,
                    r"\bnever\b[^.]*[`]?/seed-data[`]?",
                )
                self.assertNotRegex(
                    normalized_line,
                    r"(?<!never )\b(?:run|invoke|call|execute|recommend|use|emit|return)\b[^.]*[`]?/seed-data",
                )
        self.assertTrue(occurrences)

    def test_degraded_preflight_eval_has_the_complete_evidence_rubric(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        case = next(
            case
            for case in payload["evals"]
            if case["id"] == "degraded-local-preflight"
        )
        self.assertEqual(len(case.get("expectations", [])), 7)
        rubric = " ".join(
            [case.get("expected_output", ""), *case.get("expectations", [])]
        ).lower()
        for phrase in (
            "fixture setup",
            "fixture setup: /check-data (default: plan → seed → verify)",
            "fixture setup: not needed — <evidence>",
            "single /check-data invocation owns all three phases",
            "never express them as multiple skills or commands",
            "before returning",
            "both artifacts",
            "rewrite any /seed-data occurrence",
            "entrypoint is deleted",
            "complete backend and frontend happy-path/error/edge-case coverage",
            "surface is unavailable",
            "skip/inconclusive",
            "final report",
        ):
            self.assertIn(phrase, rubric)

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
