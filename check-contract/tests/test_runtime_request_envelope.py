import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_reconciliation import load_modules


class RuntimeRequestEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, _ = load_modules()

    def target(self, repo):
        return self.module.AuditTarget(
            repo=repo,
            branch="feature/proj-123",
            ticket="PROJ-123",
        )

    def test_enforced_request_derives_target_and_is_consumed_once(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            runtime = self.module.AuditRuntime(session_root=Path(temporary))
            envelope = runtime.issue_request(self.target(repo))

            started = runtime.advance(
                self.module.StartAudit(request_id=envelope.request_id)
            )
            retried = runtime.advance(
                self.module.StartAudit(request_id=envelope.request_id)
            )
            bypass = runtime.advance(
                self.module.StartAudit(primary=self.target(repo))
            )

            self.assertIsInstance(started, self.module.NeedJudgment)
            self.assertEqual(started.request_id, envelope.request_id)
            packet = packet_of(started)
            self.assertEqual(packet["request"]["id"], envelope.request_id)
            self.assertEqual(
                packet["request"]["manifest_sha256"],
                envelope.manifest_sha256,
            )
            self.assertEqual(retried.code, "REQUEST_CONSUMED")
            self.assertEqual(bypass.code, "REQUEST_REQUIRED")
            state = self.module.SessionStore(Path(temporary)).load(
                started.session
            )
            self.assertEqual(state["request_id"], envelope.request_id)

    def test_concurrent_starts_atomically_consume_one_request(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            runtime = self.module.AuditRuntime(session_root=Path(temporary))
            envelope = runtime.issue_request(self.target(repo))
            request = self.module.StartAudit(
                request_id=envelope.request_id
            )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = tuple(
                    executor.map(runtime.advance, (request, request))
                )

            self.assertEqual(
                sum(
                    isinstance(item, self.module.NeedJudgment)
                    for item in results
                ),
                1,
            )
            stopped = next(
                item
                for item in results
                if isinstance(item, self.module.AuditStopped)
            )
            self.assertEqual(stopped.code, "REQUEST_CONSUMED")

    def test_terminal_pre_session_failure_still_consumes_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing"
            runtime = self.module.AuditRuntime(session_root=root / "sessions")
            envelope = runtime.issue_request(self.target(missing))

            failed = runtime.advance(
                self.module.StartAudit(request_id=envelope.request_id)
            )
            retried = runtime.advance(
                self.module.StartAudit(request_id=envelope.request_id)
            )

            self.assertEqual(failed.code, "AUTHORITY_INVALID")
            self.assertEqual(failed.request_id, envelope.request_id)
            self.assertEqual(retried.code, "REQUEST_CONSUMED")

    def test_compound_manifest_is_authoritative_and_chains_a_before_b(self):
        with materialized_repo(
            "contract-violated-summary", "target-a"
        ) as primary, materialized_repo(
            "contract-violated-summary", "target-b"
        ) as then, tempfile.TemporaryDirectory() as temporary:
            runtime = self.module.AuditRuntime(session_root=Path(temporary))
            envelope = runtime.issue_request(
                self.target(primary), self.target(then)
            )

            result = runtime.advance(
                self.module.StartAudit(request_id=envelope.request_id)
            )

            self.assertIsInstance(result, self.module.NeedJudgment)
            self.assertEqual(result.target, "then")
            self.assertEqual(result.request_id, envelope.request_id)
            self.assertIsNotNone(result.a_closure_digest)
            state = self.module.SessionStore(Path(temporary)).load(
                result.session
            )
            self.assertEqual(state["request_id"], envelope.request_id)
            self.assertEqual(
                state["request_manifest_sha256"], envelope.manifest_sha256
            )

    def test_compound_request_rejects_substitution_and_cannot_start_b(self):
        with materialized_repo(
            "contract-violated-summary", "target-a"
        ) as primary, materialized_repo(
            "contract-violated-summary", "target-b"
        ) as then, tempfile.TemporaryDirectory() as temporary:
            runtime = self.module.AuditRuntime(session_root=Path(temporary))
            envelope = runtime.issue_request(
                self.target(primary), self.target(then)
            )

            substituted = runtime.advance(
                self.module.StartAudit(
                    primary=self.target(then),
                    request_id=envelope.request_id,
                )
            )
            standalone = runtime.advance(
                self.module.StartAudit(
                    primary=self.target(then),
                    request_id=envelope.request_id,
                )
            )

            self.assertEqual(substituted.code, "REQUEST_TARGET_MISMATCH")
            self.assertEqual(standalone.code, "REQUEST_CONSUMED")

    def test_request_identity_cannot_cross_session_roots(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            issuer = self.module.AuditRuntime(session_root=Path(first))
            envelope = issuer.issue_request(self.target(repo))
            foreign = self.module.AuditRuntime(session_root=Path(second))

            result = foreign.advance(
                self.module.StartAudit(request_id=envelope.request_id)
            )

            self.assertEqual(result.code, "REQUEST_INVALID")

    def test_orphaned_request_manifest_fails_closed_instead_of_manual_fallback(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pending = root / ".requests/pending"
            pending.mkdir(parents=True)
            (pending / ("a" * 64 + ".json")).write_text("{}\n")
            runtime = self.module.AuditRuntime(session_root=root)

            result = runtime.advance(
                self.module.StartAudit(primary=self.target(repo))
            )

            self.assertEqual(result.code, "REQUEST_INVALID")


if __name__ == "__main__":
    unittest.main(verbosity=2)
