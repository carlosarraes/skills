import hashlib
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_reconciliation import (
    code_response,
    load_modules,
    valid_code_judgment,
    write_response,
)
from test_audit_runtime_start import git


ROOT = Path(__file__).parents[2]
REPORT_SECTIONS = (
    "## Code-first observed behavior",
    "## Clause-by-clause fidelity",
    "## YAGNI and reuse",
    "## Drift reconciliation",
    "## Ordered findings",
    "## Verdict and route",
    "## Mutation attestation",
)


def reconciliation_response(
    issued,
    *,
    statuses=None,
    deviation_matches=(),
    contract_obsolete=False,
    probe_id=None,
    **judgment_overrides,
):
    packet = packet_of(issued)
    statuses = statuses or {}
    ledger_entries = {
        item["ledger_id"]: {
            "status": statuses.get(item["ledger_id"], "VERIFIED"),
            "evidence_ids": [item["evidence_id"]],
            "reason": f"{item['ledger_id']} agrees with recorded evidence.",
        }
        for item in packet["ledger_entries"]
    }
    judgment = {
        "ledger_entries": ledger_entries,
        "deviation_matches": list(deviation_matches),
        "contract_obsolete": {
            "value": contract_obsolete,
            "evidence_ids": (
                ["contract:O1"] if contract_obsolete else []
            ),
            "reason": (
                "Current authority conflicts with the approved contract."
                if contract_obsolete
                else "The approved contract remains authoritative."
            ),
        },
        "probe_id": probe_id,
    }
    judgment.update(judgment_overrides)
    return {
        "schema_version": 1,
        "session": issued.session,
        "nonce": issued.nonce,
        "packet_sha256": issued.packet_sha256,
        "kind": "reconciliation",
        "judgment": judgment,
    }


class AuditRuntimeCloseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, _ = load_modules()

    def target(self, repo, **overrides):
        values = {
            "repo": repo,
            "branch": "feature/proj-123",
            "ticket": "PROJ-123",
        }
        values.update(overrides)
        return self.module.AuditTarget(**values)

    def runtime(self, root, **overrides):
        return self.module.AuditRuntime(session_root=root, **overrides)

    def issue_reconciliation(
        self,
        repo,
        root,
        *,
        judgment=None,
        target_overrides=None,
        runtime=None,
    ):
        runtime = runtime or self.runtime(root)
        started = runtime.advance(
            self.module.StartAudit(
                self.target(repo, **(target_overrides or {}))
            )
        )
        self.assertIsInstance(started, self.module.NeedJudgment)
        write_response(
            started.response_path,
            code_response(
                started,
                judgment=judgment
                if judgment is not None
                else valid_code_judgment(packet_of(started)),
            ),
        )
        issued = runtime.advance(
            self.module.ContinueAudit(
                started.session,
                started.response_path,
            )
        )
        self.assertIsInstance(issued, self.module.NeedJudgment)
        self.assertEqual(issued.kind, "reconciliation")
        return runtime, issued

    def close(self, runtime, issued, response=None):
        write_response(
            issued.response_path,
            response or reconciliation_response(issued),
        )
        return runtime.advance(
            self.module.ContinueAudit(
                issued.session,
                issued.response_path,
            )
        )

    def report_path(self, repo):
        return (
            repo
            / ".notes/feature-proj-123/contract/v1/check-report.md"
        )

    def test_valid_reconciliation_closes_and_publishes_complete_report(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime, issued = self.issue_reconciliation(repo, root)

            result = self.close(runtime, issued)

            self.assertIsInstance(result, self.module.AuditComplete)
            self.assertEqual(result.verdict, "PASS")
            self.assertEqual(result.route, ("qa-ticket",))
            self.assertEqual(result.report_path, self.report_path(repo))
            report = result.report_path.read_bytes()
            self.assertEqual(
                result.report_sha256,
                hashlib.sha256(report).hexdigest(),
            )
            text = report.decode("utf-8")
            self.assertIn("# Contract Check: PROJ-123 — v1", text)
            for section in REPORT_SECTIONS:
                self.assertIn(section, text)
            self.assertIn("IDs: none", text)
            self.assertEqual(
                result.mutation_attestation["mutated_paths"],
                (str(result.report_path.relative_to(repo)),),
            )
            self.assertTrue(
                result.mutation_attestation["only_active_report_changed"]
            )

    def test_reconciliation_rejects_model_owned_execution_and_decisions(self):
        forbidden = (
            ("argv", ["python", "-c", "pass"]),
            ("shell", True),
            ("code", "print('unsafe')"),
            ("route", ["qa-pr"]),
            ("verdict", "PASS"),
            ("report_path", "/tmp/report"),
            ("aggregate", {"fidelity": "PASS"}),
            ("acceptance_qa_exists", True),
        )
        for field, value in forbidden:
            with self.subTest(field=field), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                runtime, issued = self.issue_reconciliation(repo, root)
                before = self.report_path(repo).read_bytes() if (
                    self.report_path(repo).exists()
                ) else None
                response = reconciliation_response(issued)
                response["judgment"][field] = value

                result = self.close(runtime, issued, response)

                self.assertIsInstance(result, self.module.AuditStopped)
                self.assertEqual(result.code, "RESPONSE_INVALID")
                after = self.report_path(repo).read_bytes() if (
                    self.report_path(repo).exists()
                ) else None
                self.assertEqual(after, before)

    def test_runtime_owned_acceptance_qa_selects_route(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            head = git(repo, "rev-parse", "HEAD")
            qa = repo / "review-evidence.md"
            qa.write_text(
                "<!-- qa-pr-evidence -->\n"
                "## QA evidence — ✅ PASS "
                f"<sub>(@ {head})</sub>\n",
                encoding="utf-8",
            )
            runtime, issued = self.issue_reconciliation(
                repo,
                Path(temporary),
                target_overrides={"narrative_paths": (qa,)},
            )

            result = self.close(runtime, issued)

            self.assertIsInstance(result, self.module.AuditComplete)
            self.assertEqual(result.route, ("qa-pr",))

    def test_prior_report_is_preserved_when_reconciliation_is_invalid(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            report = self.report_path(repo)
            report.write_bytes(b"PRIOR REPORT SENTINEL\n")
            runtime, issued = self.issue_reconciliation(
                repo,
                Path(temporary),
            )
            response = reconciliation_response(issued)
            response["judgment"]["ledger_entries"]["D99"] = {
                "status": "VERIFIED",
                "evidence_ids": ["runtime:QA-1"],
                "reason": "Fabricated ledger entry.",
            }

            result = self.close(runtime, issued, response)

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "RESPONSE_INVALID")
            self.assertEqual(
                report.read_bytes(),
                b"PRIOR REPORT SENTINEL\n",
            )

    def test_report_publication_uses_atomic_replace_and_cleans_temp(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime, issued = self.issue_reconciliation(repo, root)
            calls = []
            original = os.replace

            def recording_replace(source, destination):
                calls.append((Path(source), Path(destination)))
                return original(source, destination)

            with mock.patch("os.replace", side_effect=recording_replace):
                result = self.close(runtime, issued)

            self.assertIsInstance(result, self.module.AuditComplete)
            target_calls = [
                pair for pair in calls if pair[1] == self.report_path(repo)
            ]
            self.assertEqual(len(target_calls), 1)
            source, destination = target_calls[0]
            self.assertEqual(source.parent, destination.parent)
            self.assertFalse(source.exists())

    def test_probe_is_one_shot_disposable_and_controls_documented_drift(self):
        cases = (
            ("success", "Q1", "ACCEPTED", "PASS WITH DOCUMENTED DRIFT"),
            ("absent", None, "QUESTIONABLE", "NEEDS HUMAN REVIEW"),
        )
        for name, probe_id, drift, verdict in cases:
            with self.subTest(name=name), materialized_repo(
                "documented-drift"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                runtime, issued = self.issue_reconciliation(repo, root)
                packet = packet_of(issued)
                self.assertEqual(packet["probe_ids"], ["Q1"])

                result = self.close(
                    runtime,
                    issued,
                    reconciliation_response(issued, probe_id=probe_id),
                )

                self.assertIsInstance(result, self.module.AuditComplete)
                self.assertEqual(result.verdict, verdict)
                report = result.report_path.read_text(encoding="utf-8")
                self.assertIn(f"Documented drift: {drift}", report)
                self.assertFalse(
                    any(repo.rglob("__pycache__")),
                    "probe execution must not create target bytecode",
                )
                self.assertFalse(
                    any(root.glob("contract-audit-probe-*")),
                    "disposable probe trees must be removed",
                )

    def test_probe_failure_is_questionable_and_is_not_retried(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            ledger = (
                repo
                / ".notes/feature-proj-123/contract/v1/execution-ledger.md"
            )
            ledger.write_text(
                ledger.read_text(encoding="utf-8").replace(
                    '{"args":[0],"expect":"returns"}',
                    '{"args":[0],"expect":"raises","exception":"ValueError"}',
                ),
                encoding="utf-8",
            )
            root = Path(temporary)
            runtime, issued = self.issue_reconciliation(repo, root)
            real_run = importlib.import_module("subprocess").run
            calls = []

            def recording_run(*args, **kwargs):
                calls.append((args, kwargs))
                return real_run(*args, **kwargs)

            with mock.patch("subprocess.run", side_effect=recording_run):
                result = self.close(
                    runtime,
                    issued,
                    reconciliation_response(issued, probe_id="Q1"),
                )

            self.assertIsInstance(result, self.module.AuditComplete)
            self.assertEqual(result.verdict, "NEEDS HUMAN REVIEW")
            self.assertIn(
                "Documented drift: QUESTIONABLE",
                result.report_path.read_text(encoding="utf-8"),
            )
            probe_calls = [
                call
                for call in calls
                if call[1].get("cwd")
                and "contract-audit-probe-" in str(call[1]["cwd"])
            ]
            self.assertEqual(len(probe_calls), 1)
            self.assertFalse(probe_calls[0][1].get("shell", False))
            self.assertEqual(
                probe_calls[0][1]["env"]["PYTHONDONTWRITEBYTECODE"],
                "1",
            )
            self.assertIn("timeout", probe_calls[0][1])

    def test_every_freshness_guard_preserves_the_prior_report(self):
        class MutableAuthority:
            def __init__(self, resolver):
                self.resolver = resolver
                self.changed = False

            def __call__(self, repo, branch, ticket):
                value = self.resolver(repo, branch, ticket)
                if self.changed:
                    return {**value, "branch": "feature/stale"}
                return value

        class MutableSourceRunner:
            def __init__(self, module):
                self.delegate = module.LocalGitRunner()
                self.changed = False

            def run(self, args, *, cwd, deadline, output_limit=None):
                result = self.delegate.run(
                    args,
                    cwd=cwd,
                    deadline=deadline,
                    output_limit=output_limit,
                )
                if self.changed and args[:2] == ["diff", "--name-status"]:
                    return type(result)(
                        result.stdout + b"M\0stale.py\0",
                        result.truncated,
                        result.timed_out,
                    )
                return result

        cases = (
            "head",
            "authority",
            "contract",
            "ledger",
            "summary",
            "status",
            "prior-report",
            "packet",
            "source",
        )
        for source in cases:
            with self.subTest(source=source), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                report = self.report_path(repo)
                report.write_bytes(b"PRIOR REPORT SENTINEL\n")
                summary = repo / ".worker-results/implementation-summary.md"
                summary.parent.mkdir(parents=True, exist_ok=True)
                summary.write_text("ORIGINAL SUMMARY\n", encoding="utf-8")
                root = Path(temporary)
                authority = MutableAuthority(self.module.resolve_authority)
                runner = MutableSourceRunner(self.module)
                runtime = self.runtime(
                    root,
                    authority_resolver=authority,
                    git_runner=runner,
                )
                runtime, issued = self.issue_reconciliation(
                    repo,
                    root,
                    target_overrides={"narrative_paths": (summary,)},
                    runtime=runtime,
                )

                if source == "head":
                    extra = repo / "head-drift.txt"
                    extra.write_text("HEAD DRIFT\n", encoding="utf-8")
                    git(repo, "add", "head-drift.txt")
                    git(repo, "commit", "-m", "test: drift head")
                elif source == "authority":
                    authority.changed = True
                elif source == "contract":
                    contract = Path(
                        self.module.SessionStore(root).load(
                            issued.session
                        )["authority_guard"]["contract_path"]
                    )
                    contract.write_bytes(contract.read_bytes() + b"\n")
                elif source == "ledger":
                    ledger = Path(
                        self.module.SessionStore(root).load(
                            issued.session
                        )["ledger_guard"]["path"]
                    )
                    ledger.parent.mkdir(parents=True, exist_ok=True)
                    ledger.write_text("# Execution Ledger\n", encoding="utf-8")
                elif source == "summary":
                    summary.write_text("CHANGED SUMMARY\n", encoding="utf-8")
                elif source == "status":
                    (repo / "status-drift.txt").write_text(
                        "STATUS DRIFT\n",
                        encoding="utf-8",
                    )
                elif source == "prior-report":
                    report.write_bytes(b"CHANGED PRIOR REPORT\n")
                elif source == "packet":
                    os.chmod(issued.packet_path, 0o600)
                    issued.packet_path.write_bytes(
                        issued.packet_path.read_bytes() + b" "
                    )
                elif source == "source":
                    runner.changed = True

                result = self.close(runtime, issued)

                self.assertIsInstance(result, self.module.AuditStopped)
                self.assertIn(
                    result.code,
                    {"SESSION_INVALID", "FRESHNESS_FAILED"},
                )
                expected = (
                    b"CHANGED PRIOR REPORT\n"
                    if source == "prior-report"
                    else b"PRIOR REPORT SENTINEL\n"
                )
                self.assertEqual(report.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
