import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_close import reconciliation_response
from test_audit_runtime_reconciliation import load_modules, valid_code_judgment


ROOT = Path(__file__).parents[2]
CLI = ROOT / "check-contract" / "scripts" / "check_contract.py"


class CheckContractCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime_module, _ = load_modules()

    def run_cli(self, cwd, *args, session_root):
        session_root.mkdir(parents=True, exist_ok=True)
        environment = {
            **os.environ,
            "TMPDIR": str(session_root),
        }
        return subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_start_from_foreign_cwd_emits_canonical_public_json(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            foreign_cwd = root / "foreign"
            foreign_cwd.mkdir()

            completed = self.run_cli(
                foreign_cwd,
                "start",
                "--repo",
                repo,
                "--branch",
                "feature/proj-123",
                "--ticket",
                "PROJ-123",
                "--deadline-seconds",
                "120",
                session_root=root / "sessions",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            public = json.loads(completed.stdout)
            self.assertEqual(
                completed.stdout,
                json.dumps(
                    public, sort_keys=True, separators=(",", ":")
                )
                + "\n",
            )
            self.assertEqual(
                (public["result"], public["target"], public["kind"]),
                ("NeedJudgment", "primary", "code"),
            )
            self.assertNotIn(str(repo), completed.stdout)
            self.assertNotIn("feature/proj-123", completed.stdout)
            self.assertNotIn("PROJ-123", completed.stdout)
            self.assertNotIn("authority_guard", completed.stdout)
            self.assertNotIn("target_identity", completed.stdout)

            issued = SimpleNamespace(
                **{
                    **public,
                    "packet_path": Path(public["packet_path"]),
                    "response_path": Path(public["response_path"]),
                }
            )
            packet = packet_of(issued)
            issued.response_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "session": issued.session,
                        "nonce": issued.nonce,
                        "packet_sha256": issued.packet_sha256,
                        "kind": "code",
                        "judgment": valid_code_judgment(packet),
                    }
                ),
                encoding="utf-8",
            )
            continued = self.run_cli(
                foreign_cwd,
                "continue",
                "--session",
                issued.session,
                "--response",
                issued.response_path,
                session_root=root / "sessions",
            )
            self.assertEqual(continued.returncode, 0, continued.stderr)
            reconciliation_public = json.loads(continued.stdout)
            self.assertEqual(
                (
                    reconciliation_public["result"],
                    reconciliation_public["kind"],
                ),
                ("NeedJudgment", "reconciliation"),
            )
            reconciliation = SimpleNamespace(
                **{
                    **reconciliation_public,
                    "packet_path": Path(
                        reconciliation_public["packet_path"]
                    ),
                    "response_path": Path(
                        reconciliation_public["response_path"]
                    ),
                }
            )
            reconciliation.response_path.write_text(
                json.dumps(reconciliation_response(reconciliation)),
                encoding="utf-8",
            )
            closed = self.run_cli(
                foreign_cwd,
                "continue",
                "--session",
                reconciliation.session,
                "--response",
                reconciliation.response_path,
                session_root=root / "sessions",
            )
            self.assertEqual(closed.returncode, 0, closed.stderr)
            self.assertEqual(
                json.loads(closed.stdout)["result"],
                "AuditComplete",
            )

    def test_audit_stop_uses_exit_two_and_canonical_json(self):
        with materialized_repo(
            "contract-violated-summary", "target-a"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            completed = self.run_cli(
                root,
                "start",
                "--repo",
                repo,
                "--branch",
                "feature/proj-123",
                "--ticket",
                "PROJ-123",
                session_root=root / "sessions",
            )

            self.assertEqual(completed.returncode, 2)
            public = json.loads(completed.stdout)
            self.assertEqual(public["result"], "AuditStopped")
            self.assertEqual(public["code"], "AUTHORITY_INVALID")
            self.assertEqual(
                completed.stdout,
                json.dumps(
                    public, sort_keys=True, separators=(",", ":")
                )
                + "\n",
            )
            self.assertEqual(completed.stderr, "")

    def test_enforced_start_uses_only_trusted_request_identity(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            temp_root = root / "sessions"
            runtime = self.runtime_module.AuditRuntime(
                session_root=temp_root / "contract-audit-sessions"
            )
            envelope = runtime.issue_request(
                self.runtime_module.AuditTarget(
                    repo=repo,
                    branch="feature/proj-123",
                    ticket="PROJ-123",
                )
            )

            completed = self.run_cli(
                root,
                "start",
                "--request-id",
                envelope.request_id,
                session_root=temp_root,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            public = json.loads(completed.stdout)
            self.assertEqual(public["request_id"], envelope.request_id)
            self.assertNotIn(str(repo), completed.stdout)

    def test_unavailable_broker_fails_closed_as_canonical_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "start",
                    "--request-id",
                    "a" * 64,
                ],
                cwd=root,
                env={
                    **os.environ,
                    "CHECK_CONTRACT_BROKER_SOCKET": str(
                        root / "missing.sock"
                    ),
                    "CHECK_CONTRACT_CLIENT_ROOT": str(root / "client"),
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stderr, "")
            public = json.loads(completed.stdout)
            self.assertEqual(public["result"], "AuditStopped")
            self.assertEqual(public["code"], "BROKER_UNAVAILABLE")

    def test_public_stop_sanitizes_internal_target_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            foreign_cwd = root / "foreign"
            foreign_cwd.mkdir()
            missing_repo = root / "PRIVATE_REPO_CAPABILITY"
            branch = "private/branch-capability"
            ticket = "PRIVATE-987"

            completed = self.run_cli(
                foreign_cwd,
                "start",
                "--repo",
                missing_repo,
                "--branch",
                branch,
                "--ticket",
                ticket,
                session_root=root / "sessions",
            )

            self.assertEqual(completed.returncode, 2)
            public = json.loads(completed.stdout)
            self.assertEqual(public["result"], "AuditStopped")
            self.assertEqual(public["code"], "AUTHORITY_INVALID")
            self.assertEqual(public["reason"], "audit stopped")
            self.assertNotIn(str(missing_repo), completed.stdout)
            self.assertNotIn(branch, completed.stdout)
            self.assertNotIn(ticket, completed.stdout)
            for capability in (
                "session",
                "nonce",
                "packet_path",
                "response_path",
                "next_command",
            ):
                self.assertNotIn(capability, public)
            self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
