import tempfile
import sys
import unittest
from pathlib import Path
from unittest import mock

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_close import reconciliation_response
from test_audit_runtime_reconciliation import (
    code_response,
    load_modules,
    valid_code_judgment,
    write_response,
)
from test_audit_runtime_start import FakeClock


class RuntimeFinalizationGraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, _ = load_modules()

    def target(self, repo):
        return self.module.AuditTarget(
            repo=repo,
            branch="feature/proj-123",
            ticket="PROJ-123",
        )

    def runtime(self, root, **overrides):
        return self.module.AuditRuntime(session_root=root, **overrides)

    def issue_reconciliation(self, repo, root, runtime):
        started = runtime.advance(
            self.module.StartAudit(self.target(repo))
        )
        write_response(
            started.response_path,
            code_response(
                started,
                judgment=valid_code_judgment(packet_of(started)),
            ),
        )
        issued = runtime.advance(
            self.module.ContinueAudit(
                started.session, started.response_path
            )
        )
        self.assertEqual(issued.kind, "reconciliation")
        return runtime, issued

    def close(self, runtime, issued):
        write_response(
            issued.response_path, reconciliation_response(issued)
        )
        return runtime.advance(
            self.module.ContinueAudit(
                issued.session, issued.response_path
            )
        )

    @staticmethod
    def report_path(repo):
        return repo / ".notes/feature-proj-123/contract/v1/check-report.md"

    def issue_with_clock(self, repo, root):
        clock = FakeClock()
        runtime = self.runtime(root, clock=clock)
        _, issued = self.issue_reconciliation(repo, root, runtime)
        return clock, runtime, issued

    def test_reconciliation_completes_at_306_and_328_seconds(self):
        for elapsed in (306, 328):
            with self.subTest(elapsed=elapsed), materialized_repo(
                "documented-drift"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                clock, runtime, issued = self.issue_with_clock(repo, root)
                clock.value = 1000 + elapsed

                result = self.close(runtime, issued)

                self.assertIsInstance(result, self.module.AuditComplete)
                self.assertEqual(result.deadline_stage, "finalization-grace")
                self.assertTrue(result.report_path.is_file())

    def test_reconciliation_expires_at_345_seconds_and_publishes_nothing(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clock, runtime, issued = self.issue_with_clock(repo, root)
            clock.value = 1345
            write_response(
                issued.response_path,
                reconciliation_response(issued),
            )

            result = runtime.advance(
                self.module.ContinueAudit(
                    issued.session, issued.response_path
                )
            )

            self.assertEqual(result.code, "DEADLINE_EXPIRED")
            self.assertEqual(
                result.deadline_stage, "reconciliation-finalization"
            )
            self.assertFalse(self.report_path(repo).exists())

    def test_grace_is_not_available_to_code_stage(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clock = FakeClock()
            runtime = self.runtime(root, clock=clock)
            started = runtime.advance(
                self.module.StartAudit(self.target(repo))
            )
            write_response(started.response_path, code_response(started))
            clock.value = 1306

            result = runtime.advance(
                self.module.ContinueAudit(
                    started.session, started.response_path
                )
            )

            self.assertEqual(result.code, "DEADLINE_EXPIRED")
            self.assertEqual(result.deadline_stage, "normal")

    def test_grace_still_rejects_freshness_mutation(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clock, runtime, issued = self.issue_with_clock(repo, root)
            (repo / "unexpected.txt").write_text("mutation\n")
            clock.value = 1306

            result = self.close(runtime, issued)

            self.assertEqual(result.code, "FRESHNESS_FAILED")
            self.assertFalse(self.report_path(repo).exists())

    def test_grace_still_rejects_objective_semantic_mismatch(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clock, runtime, issued = self.issue_with_clock(repo, root)
            response = reconciliation_response(issued)
            response["judgment"]["semantic_generation"] = "forged"
            write_response(issued.response_path, response)
            clock.value = 1306

            result = runtime.advance(
                self.module.ContinueAudit(
                    issued.session, issued.response_path
                )
            )

            self.assertEqual(result.code, "RESPONSE_INVALID")
            self.assertFalse(self.report_path(repo).exists())

    def test_publication_crossing_grace_boundary_is_rolled_back(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = self.report_path(repo)
            report_path.write_bytes(b"PRIOR REPORT\n")
            clock, runtime, issued = self.issue_with_clock(repo, root)
            clock.value = 1344.5
            real_publish = self.module.publish_atomic
            before_guard = self.module._identity_guard_path(report_path)
            before_state = self.module.capture_target_state(repo)

            def expire_before_commit(*args, **kwargs):
                clock.value = 1345
                return real_publish(*args, **kwargs)

            with mock.patch.object(
                self.module,
                "publish_atomic",
                side_effect=expire_before_commit,
            ):
                result = self.close(runtime, issued)

            self.assertEqual(result.code, "DEADLINE_EXPIRED")
            self.assertEqual(
                result.deadline_stage, "reconciliation-finalization"
            )
            self.assertTrue(result.prior_report_preserved)
            self.assertTrue(result.zero_target_writes)
            self.assertEqual(
                self.module._identity_guard_path(report_path), before_guard
            )
            self.assertEqual(
                self.module.capture_target_state(repo), before_state
            )

    def test_replace_cannot_cross_the_reserved_publication_boundary(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = self.report_path(repo)
            report_path.write_bytes(b"PRIOR REPORT\n")
            clock, runtime, issued = self.issue_with_clock(repo, root)
            clock.value = 1344.5
            before_guard = self.module._identity_guard_path(report_path)
            before_state = self.module.capture_target_state(repo)
            report_module = sys.modules["audit_report"]
            real_replace = report_module.os.replace

            def replace_after_boundary(*args, **kwargs):
                clock.value = 1345
                return real_replace(*args, **kwargs)

            with mock.patch.object(
                report_module.os,
                "replace",
                side_effect=replace_after_boundary,
            ) as replaced:
                result = self.close(runtime, issued)

            self.assertEqual(result.code, "DEADLINE_EXPIRED")
            self.assertEqual(
                result.deadline_stage, "reconciliation-finalization"
            )
            self.assertFalse(replaced.called)
            self.assertTrue(result.prior_report_preserved)
            self.assertTrue(result.zero_target_writes)
            self.assertEqual(
                self.module._identity_guard_path(report_path), before_guard
            )
            self.assertEqual(
                self.module.capture_target_state(repo), before_state
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
