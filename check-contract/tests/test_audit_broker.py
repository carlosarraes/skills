import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from runtime_fixtures import materialized_repo
from test_audit_runtime_close import reconciliation_response
from test_audit_runtime_reconciliation import (
    load_modules,
    valid_code_judgment,
)


ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "check-contract" / "scripts"
EVALS = ROOT / "check-contract" / "evals"


def load_broker():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import audit_broker

        return audit_broker
    finally:
        sys.path.pop(0)


def load_harness():
    import importlib.util

    path = EVALS / "live_harness.py"
    spec = importlib.util.spec_from_file_location("live_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AuditBrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime_module, _ = load_modules()
        cls.broker_module = load_broker()
        cls.harness = load_harness()

    def target(self, repo):
        return self.runtime_module.AuditTarget(
            repo=repo,
            branch="feature/proj-123",
            ticket="PROJ-123",
        )

    def start_broker(self, root, repo):
        host_private = root / "host-private"
        runtime = self.runtime_module.AuditRuntime(
            session_root=host_private / "sessions"
        )
        envelope = runtime.issue_request(self.target(repo))
        socket_path = root / "broker-channel" / "audit.sock"
        server = self.broker_module.AuditBrokerServer(
            socket_path,
            runtime,
            envelope,
            public_targets={
                repo.resolve(): Path("/tmp/workspace/fixture/target")
            },
        )
        return host_private, envelope, socket_path, server

    def test_report_mapping_is_relative_to_the_authorized_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / ".notes/ancestor/repository"
            notes_report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            docs_report = (
                repo
                / "ai_docs/feature-proj-123/contract/v1/check-report.md"
            )
            public = Path("/tmp/workspace/fixture/target")

            self.assertEqual(
                self.broker_module.subject_report_path(
                    repo, notes_report, public
                ),
                "/tmp/workspace/fixture/target/.notes/feature-proj-123/contract/v1/check-report.md",
            )
            self.assertEqual(
                self.broker_module.subject_report_path(
                    repo, docs_report, public
                ),
                "/tmp/workspace/fixture/target/ai_docs/feature-proj-123/contract/v1/check-report.md",
            )
            with self.assertRaises(self.broker_module.BrokerError):
                self.broker_module.subject_report_path(
                    repo, root / "outside/check-report.md", public
                )

    def test_broker_rejects_missing_public_mapping_before_start(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.runtime_module.AuditRuntime(
                session_root=root / "sessions"
            )
            envelope = runtime.issue_request(self.target(repo))
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )

            with self.assertRaises(ValueError):
                self.broker_module.AuditBrokerServer(
                    root / "broker/audit.sock",
                    runtime,
                    envelope,
                    public_targets={},
                )

            self.assertFalse(report.exists())
            self.assertEqual(
                self.runtime_module.RequestStore(
                    runtime.session_root
                ).enforced_id(),
                envelope.request_id,
            )

    def test_compound_target_b_mapping_is_prevalidated_and_distinct(self):
        with materialized_repo(
            "documented-drift"
        ) as primary, materialized_repo(
            "contract-compliant-overengineered"
        ) as then, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.runtime_module.AuditRuntime(
                session_root=root / "sessions"
            )
            envelope = runtime.issue_request(
                self.target(primary), self.target(then)
            )
            primary_public = Path("/tmp/workspace/fixture/primary")

            for mappings in (
                {primary.resolve(): primary_public},
                {
                    primary.resolve(): primary_public,
                    then.resolve(): primary_public,
                },
            ):
                with self.subTest(mappings=mappings), self.assertRaises(
                    ValueError
                ):
                    self.broker_module.AuditBrokerServer(
                        root / "broker/audit.sock",
                        runtime,
                        envelope,
                        public_targets=mappings,
                    )

            self.assertEqual(
                self.runtime_module.RequestStore(
                    runtime.session_root
                ).enforced_id(),
                envelope.request_id,
            )

    def test_post_publication_mapping_failure_never_claims_zero_writes(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.runtime_module.AuditRuntime(
                session_root=root / "sessions"
            )
            envelope = runtime.issue_request(self.target(repo))
            broker = self.broker_module.HostAuditBroker(
                runtime,
                envelope,
                {repo.resolve(): Path("/tmp/workspace/fixture/target")},
            )
            complete = self.runtime_module.AuditComplete(
                verdict="ready",
                route=(),
                report_path=root / "outside/check-report.md",
                report_sha256="0" * 64,
                mutation_attestation={},
            )

            with self.assertRaises(
                self.broker_module.BrokerError
            ) as raised:
                broker._export(complete, repo.resolve())

            stopped = broker._stopped(
                raised.exception.code,
                prior_report_preserved=(
                    raised.exception.prior_report_preserved
                ),
                zero_target_writes=raised.exception.zero_target_writes,
            )
            self.assertFalse(stopped["prior_report_preserved"])
            self.assertFalse(stopped["zero_target_writes"])

            with mock.patch.object(
                self.broker_module,
                "subject_report_path",
                side_effect=OSError("mapping storage unavailable"),
            ), self.assertRaises(
                self.broker_module.BrokerError
            ) as unexpected:
                broker._export(complete, repo.resolve())

            self.assertFalse(unexpected.exception.prior_report_preserved)
            self.assertFalse(unexpected.exception.zero_target_writes)

            with mock.patch.object(
                self.broker_module,
                "subject_report_path",
                side_effect=RuntimeError("mapping symlink loop"),
            ), self.assertRaises(
                self.broker_module.BrokerError
            ) as runtime_failure:
                broker._export(complete, repo.resolve())

            self.assertFalse(
                runtime_failure.exception.prior_report_preserved
            )
            self.assertFalse(runtime_failure.exception.zero_target_writes)

    def test_subject_cannot_replace_manifest_or_erase_consumption_ledger(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, materialized_repo(
            "documented-drift"
        ) as other, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host_private, envelope, socket_path, server = self.start_broker(
                root, repo
            )
            run_root = root / "run"
            (run_root / "fixture/target").mkdir(parents=True)
            with server.running():
                attack = self.harness.isolated_subject_command(
                    run_root,
                    {"target": repo},
                    ROOT,
                    [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; import sys; "
                            "blocked=False; "
                            "target=Path('/tmp/workspace/fixture/target/subject-write'); "
                            "\ntry: target.write_text('forged')\n"
                            "except OSError: blocked=True\n"
                            f"sys.exit(0 if blocked and not Path({str(host_private)!r}).exists() else 1)"
                        ),
                    ],
                    broker_socket=socket_path,
                )
                attempted = subprocess.run(
                    attack, capture_output=True, text=True
                )
                self.assertEqual(attempted.returncode, 0, attempted.stderr)

                bypass = self.harness.isolated_subject_command(
                    run_root,
                    {"target": repo},
                    ROOT,
                    [
                        "env",
                        "-u",
                        "CHECK_CONTRACT_BROKER_SOCKET",
                        sys.executable,
                        "/tmp/check-contract-runtime/check-contract/scripts/check_contract.py",
                        "start",
                    ],
                    broker_socket=socket_path,
                )
                bypassed = subprocess.run(
                    bypass, capture_output=True, text=True
                )
                self.assertEqual(bypassed.returncode, 2)
                self.assertIn("requires its host audit broker", bypassed.stderr)

                direct = self.harness.isolated_subject_command(
                    run_root,
                    {"target": repo},
                    ROOT,
                    [
                        sys.executable,
                        "-c",
                        (
                            "import sys; "
                            "sys.path.insert(0, '/tmp/check-contract-runtime/check-contract/scripts'); "
                            "from audit_runtime import AuditRuntime, AuditTarget, StartAudit; "
                            "from pathlib import Path; "
                            "r=AuditRuntime().advance(StartAudit(AuditTarget(Path('/tmp/workspace/fixture/target'), 'feature/proj-123', 'PROJ-123'))); "
                            "print(r.code)"
                        ),
                    ],
                    broker_socket=socket_path,
                )
                direct_result = subprocess.run(
                    direct, capture_output=True, text=True
                )
                self.assertEqual(
                    direct_result.returncode, 0, direct_result.stderr
                )
                self.assertEqual(direct_result.stdout.strip(), "BROKER_REQUIRED")

                forged = self.broker_module.broker_call(
                    socket_path,
                    {
                        "operation": "start",
                        "request_id": envelope.request_id,
                        "primary": {"repo": str(other)},
                    },
                )
                started = self.broker_module.broker_call(
                    socket_path,
                    {
                        "operation": "start",
                        "request_id": envelope.request_id,
                    },
                )
                retried = self.broker_module.broker_call(
                    socket_path,
                    {
                        "operation": "start",
                        "request_id": envelope.request_id,
                    },
                )

            self.assertEqual(forged["code"], "BROKER_REQUEST_INVALID")
            self.assertEqual(started["result"], "NeedJudgment")
            self.assertEqual(retried["code"], "REQUEST_CONSUMED")
            serialized = json.dumps(started, sort_keys=True)
            self.assertNotIn(str(host_private), serialized)
            self.assertNotIn(str(repo), serialized)
            self.assertNotIn(str(other), serialized)

    def run_subject_cli(
        self, run_root, repo, socket_path, *args, request_id=None
    ):
        argv = [
            sys.executable,
            "/tmp/check-contract-runtime/check-contract/scripts/check_contract.py",
            *map(str, args),
        ]
        if request_id is not None:
            argv = [
                "env",
                f"CHECK_CONTRACT_REQUEST_ID={request_id}",
                *argv,
            ]
        command = self.harness.isolated_subject_command(
            run_root,
            {"target": repo},
            ROOT,
            argv,
            broker_socket=socket_path,
        )
        return subprocess.run(command, capture_output=True, text=True)

    @staticmethod
    def host_client_path(run_root, subject_path):
        subject = Path(subject_path)
        return run_root / subject.relative_to("/tmp/workspace")

    def write_subject_response(self, run_root, public, judgment):
        response = {
            "schema_version": 1,
            "session": public["session"],
            "nonce": public["nonce"],
            "packet_sha256": public["packet_sha256"],
            "kind": public["kind"],
            "judgment": judgment,
        }
        path = self.host_client_path(run_root, public["response_path"])
        path.write_text(json.dumps(response), encoding="utf-8")

    def test_broker_start_uses_exact_environment_capability(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, envelope, socket_path, server = self.start_broker(root, repo)
            run_root = root / "run"
            (run_root / "fixture/target").mkdir(parents=True)

            with server.running():
                mismatch = self.run_subject_cli(
                    run_root,
                    repo,
                    socket_path,
                    "start",
                    request_id="f" * 64,
                )
                started = self.run_subject_cli(
                    run_root,
                    repo,
                    socket_path,
                    "start",
                    request_id=envelope.request_id,
                )

            self.assertEqual(mismatch.returncode, 2, mismatch.stderr)
            self.assertEqual(
                json.loads(mismatch.stdout)["code"],
                "BROKER_REQUEST_INVALID",
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertEqual(json.loads(started.stdout)["request_id"], envelope.request_id)

    def test_read_only_bwrap_subject_reaches_host_owned_audit_complete(self):
        with materialized_repo(
            "documented-drift"
        ) as source_repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / ".notes/ancestor/repository"
            shutil.copytree(source_repo, repo)
            before = self.runtime_module.capture_target_state(repo)
            host_private, envelope, socket_path, server = self.start_broker(
                root, repo
            )
            run_root = root / "run"
            (run_root / "fixture/target").mkdir(parents=True)

            with server.running():
                started_process = self.run_subject_cli(
                    run_root,
                    repo,
                    socket_path,
                    "start",
                    request_id=envelope.request_id,
                )
                self.assertEqual(
                    started_process.returncode, 0, started_process.stderr
                )
                started = json.loads(started_process.stdout)
                client_packet_path = self.host_client_path(
                    run_root, started["packet_path"]
                )
                code_packet = json.loads(client_packet_path.read_text())
                client_packet_path.write_text(
                    '{"forged":"subject-local-copy"}\n',
                    encoding="utf-8",
                )
                self.write_subject_response(
                    run_root,
                    started,
                    valid_code_judgment(code_packet),
                )

                reconciliation_process = self.run_subject_cli(
                    run_root,
                    repo,
                    socket_path,
                    "continue",
                    "--session",
                    started["session"],
                    "--response",
                    started["response_path"],
                )
                self.assertEqual(
                    reconciliation_process.returncode,
                    0,
                    reconciliation_process.stderr,
                )
                reconciliation = json.loads(reconciliation_process.stdout)
                issued = SimpleNamespace(
                    **{
                        **reconciliation,
                        "packet_path": self.host_client_path(
                            run_root, reconciliation["packet_path"]
                        ),
                        "response_path": self.host_client_path(
                            run_root, reconciliation["response_path"]
                        ),
                    }
                )
                response = reconciliation_response(issued)
                response["judgment"]["contract_obsolete"]["reason"] = (
                    "SUBJECT_MARKER must never become report bytes."
                )
                self.host_client_path(
                    run_root, reconciliation["response_path"]
                ).write_text(json.dumps(response), encoding="utf-8")

                complete_process = self.run_subject_cli(
                    run_root,
                    repo,
                    socket_path,
                    "continue",
                    "--session",
                    reconciliation["session"],
                    "--response",
                    reconciliation["response_path"],
                )

            self.assertEqual(
                complete_process.returncode, 0, complete_process.stderr
            )
            complete = json.loads(complete_process.stdout)
            self.assertEqual(complete["result"], "AuditComplete")
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            self.assertTrue(report.is_file())
            report_bytes = report.read_bytes()
            self.assertTrue(report_bytes.startswith(b"# Contract Check:"))
            self.assertIn(b"## Verdict and route", report_bytes)
            self.assertEqual(
                complete["report_sha256"],
                hashlib.sha256(report_bytes).hexdigest(),
            )
            self.assertEqual(
                complete["report_path"],
                "/tmp/workspace/fixture/target/.notes/feature-proj-123/contract/v1/check-report.md",
            )
            self.assertNotIn(str(repo), complete_process.stdout)
            after = self.runtime_module.capture_target_state(repo)
            attestation = self.runtime_module.mutation_attestation(
                before,
                after,
                ".notes/feature-proj-123/contract/v1/check-report.md",
            )
            self.assertTrue(attestation["only_active_report_changed"])
            self.assertTrue(complete["mutation_attestation"]["only_active_report_changed"])
            self.assertFalse((host_private / "leaked-to-subject").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
