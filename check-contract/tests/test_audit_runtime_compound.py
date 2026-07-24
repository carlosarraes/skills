import json
import tempfile
import unittest
from pathlib import Path

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_close import reconciliation_response
from test_audit_runtime_reconciliation import (
    code_response,
    load_modules,
    valid_code_judgment,
    write_response,
)
from test_audit_runtime_start import RecordingRunner


class AuditRuntimeCompoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, _ = load_modules()

    def target(self, repo, *, narratives=()):
        return self.module.AuditTarget(
            repo=repo,
            branch="feature/proj-123",
            ticket="PROJ-123",
            narrative_paths=tuple(narratives),
        )

    def test_authority_stopped_primary_seals_before_fresh_then_run(self):
        with materialized_repo(
            "contract-violated-summary", "target-a"
        ) as primary, materialized_repo(
            "contract-violated-summary", "target-b"
        ) as then, tempfile.TemporaryDirectory() as temporary:
            session_root = Path(temporary)
            prior_report = (
                primary
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            prior_bytes = prior_report.read_bytes()
            runner = RecordingRunner(self.module.LocalGitRunner())
            result = self.module.AuditRuntime(
                session_root=session_root,
                git_runner=runner,
            ).advance(
                self.module.StartAudit(
                    primary=self.target(primary),
                    then=self.target(then),
                )
            )

            self.assertIsInstance(result, self.module.NeedJudgment)
            self.assertEqual((result.target, result.kind), ("then", "code"))
            self.assertRegex(result.a_closure_digest, r"^[0-9a-f]{64}$")
            self.assertEqual(
                dict(result.closed_target),
                {
                    "target": "primary",
                    "outcome": "authority-stopped",
                    "zero_writes": True,
                    "report_only_write": False,
                    "prior_report_preserved": True,
                    "closure_digest": result.a_closure_digest,
                },
            )
            self.assertEqual(prior_report.read_bytes(), prior_bytes)
            self.assertEqual(len(tuple(session_root.iterdir())), 2)
            b_state = self.module.SessionStore(session_root).load(
                result.session
            )
            boundary = json.dumps(
                {"packet": packet_of(result), "state": b_state},
                sort_keys=True,
            )
            self.assertNotIn(str(primary), boundary)
            self.assertNotIn("STALE_REPORT_SENTINEL", boundary)
            self.assertNotIn(
                "0c3a0ba9fc813c9a22e1f642126175aea6d0642e",
                boundary,
            )
            self.assertTrue(runner.calls)
            self.assertTrue(
                all(call[1] == then for call in runner.calls)
            )

    def test_published_primary_closes_before_then_and_erases_identity(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as primary, materialized_repo(
            "contract-violated-summary", "target-b"
        ) as then, tempfile.TemporaryDirectory() as temporary:
            session_root = Path(temporary)
            secret = primary / "primary-only-narrative.md"
            secret.write_text(
                "PRIMARY_CLOSURE_SECRET must not cross\n",
                encoding="utf-8",
            )
            runner = RecordingRunner(self.module.LocalGitRunner())
            runtime = self.module.AuditRuntime(
                session_root=session_root,
                git_runner=runner,
            )
            started = runtime.advance(
                self.module.StartAudit(
                    primary=self.target(primary, narratives=(secret,)),
                    then=self.target(then),
                )
            )
            self.assertEqual(started.target, "primary")
            write_response(
                started.response_path,
                code_response(
                    started,
                    judgment=valid_code_judgment(packet_of(started)),
                ),
            )
            reconciled = runtime.advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            write_response(
                reconciled.response_path,
                reconciliation_response(reconciled),
            )

            result = runtime.advance(
                self.module.ContinueAudit(
                    reconciled.session,
                    reconciled.response_path,
                )
            )

            self.assertIsInstance(result, self.module.NeedJudgment)
            self.assertEqual((result.target, result.kind), ("then", "code"))
            self.assertEqual(result.closed_target["outcome"], "closed")
            self.assertFalse(result.closed_target["zero_writes"])
            self.assertTrue(result.closed_target["report_only_write"])
            self.assertTrue(result.closed_target["prior_report_preserved"])
            report = (
                primary
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            self.assertTrue(report.is_file())
            b_state = self.module.SessionStore(session_root).load(
                result.session
            )
            boundary = json.dumps(
                {"packet": packet_of(result), "state": b_state},
                sort_keys=True,
            )
            self.assertNotIn(str(primary), boundary)
            self.assertNotIn("PRIMARY_CLOSURE_SECRET", boundary)
            self.assertNotIn(
                "d3d02eaa6d8dc88fc43611c57f1dd89948bdd4c3",
                boundary,
            )
            self.assertEqual(len(tuple(session_root.iterdir())), 2)
            call_repositories = [call[1] for call in runner.calls]
            first_then = call_repositories.index(then)
            self.assertNotIn(primary, call_repositories[first_then:])


if __name__ == "__main__":
    unittest.main()
