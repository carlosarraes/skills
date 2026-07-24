import hashlib
import importlib
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime_fixtures import materialized_repo, packet_of


ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "check-contract" / "scripts"
BASE = "7aa39139c43dfcb9ff54474abfbacc9da3799937"


def load_runtime():
    sys.path.insert(0, str(SCRIPTS))
    try:
        for name in ("audit_runtime", "audit_evidence", "audit_session"):
            sys.modules.pop(name, None)
        return importlib.import_module("audit_runtime")
    finally:
        sys.path.pop(0)


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class FakeClock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value


class RecordingRunner:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = []

    def run(self, args, *, cwd, deadline, output_limit=None):
        self.calls.append((tuple(args), Path(cwd), deadline, output_limit))
        return self.delegate.run(
            args,
            cwd=cwd,
            deadline=deadline,
            output_limit=output_limit,
        )


class ExplodingRunner:
    def run(self, args, *, cwd, deadline, output_limit=None):
        raise AssertionError("evidence capture ran before contract validation")


class AuditRuntimeStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_runtime()

    def target(self, repo, **overrides):
        values = {
            "repo": repo,
            "branch": "feature/proj-123",
            "ticket": "PROJ-123",
        }
        values.update(overrides)
        return self.module.AuditTarget(**values)

    def runtime(self, session_root, **overrides):
        values = {"session_root": session_root}
        values.update(overrides)
        return self.module.AuditRuntime(**values)

    def test_start_records_authority_clause_ids_and_filtered_code(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            prior = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            summary = repo / ".worker-results/implementation-summary.md"
            pr = repo / "pr-description.md"
            prior.parent.mkdir(parents=True, exist_ok=True)
            summary.parent.mkdir(parents=True, exist_ok=True)
            prior.write_text("PRIOR_REPORT_SENTINEL\n", encoding="utf-8")
            summary.write_text("SUMMARY_SENTINEL\n", encoding="utf-8")
            pr.write_text("PR_NARRATIVE_SENTINEL\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "docs: add author narratives")
            head = git(repo, "rev-parse", "HEAD")

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(
                    self.target(repo, narrative_paths=(pr,))
                )
            )

            self.assertIsInstance(result, self.module.NeedJudgment)
            packet = packet_of(result)
            self.assertEqual(packet["authority"]["base_sha"], BASE)
            self.assertEqual(packet["authority"]["head_sha"], head)
            self.assertEqual(
                packet["clause_ids"],
                [
                    "O1",
                    "B1",
                    "B2",
                    "B3",
                    "B4",
                    "N1",
                    "N2",
                    "N3",
                    "N4",
                    "I1",
                    "I2",
                    "C1",
                    "C2",
                    "R1",
                    "R2",
                    "R3",
                    "S1",
                    "S2",
                    "K-MODULES",
                    "K-RUNTIME-DEPENDENCIES",
                    "K-ABSTRACTIONS",
                    "K-CONFIGURATION",
                    "K-PUBLIC-INTERFACES",
                    "A-B1",
                    "A-B2",
                    "A-B3",
                    "A-B4",
                ],
            )
            serialized = json.dumps(packet, sort_keys=True)
            for forbidden in (
                "PRIOR_REPORT_SENTINEL",
                "SUMMARY_SENTINEL",
                "PR_NARRATIVE_SENTINEL",
                "# Execution Ledger",
            ):
                self.assertNotIn(forbidden, serialized)
            self.assertEqual(
                [item["path"] for item in packet["changed_paths"]],
                ["src/checkout.py", "src/pricing.py", "tests/test_checkout.py"],
            )

    def test_shared_ai_docs_authority_filters_both_contract_roots(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            git(repo, "mv", ".notes", "ai_docs")
            git(repo, "commit", "-m", "docs: relocate approved authority")
            head = git(repo, "rev-parse", "HEAD")

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(self.target(repo))
            )

            packet = packet_of(result)
            self.assertEqual(packet["authority"]["base_sha"], BASE)
            self.assertEqual(packet["authority"]["head_sha"], head)
            serialized = json.dumps(packet, sort_keys=True)
            self.assertNotIn('"approved_by"', serialized)

    def test_malformed_contract_hard_stops_before_evidence(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            contract = (
                repo / ".notes/feature-proj-123/contract/v1/contract.md"
            )
            approval = contract.with_name("approval.json")
            contract.write_text(
                contract.read_text(encoding="utf-8").replace(
                    "## Required behaviors",
                    "## Outcome",
                ),
                encoding="utf-8",
            )
            value = json.loads(approval.read_text(encoding="utf-8"))
            value["contract_sha256"] = hashlib.sha256(
                contract.read_bytes()
            ).hexdigest()
            approval.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = self.runtime(
                Path(temporary),
                git_runner=ExplodingRunner(),
            ).advance(self.module.StartAudit(self.target(repo)))

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "CONTRACT_INVALID")
            self.assertTrue(result.zero_target_writes)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_capture_is_single_batched_and_reuse_query_is_closed(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            runner = RecordingRunner(self.module.LocalGitRunner())
            result = self.runtime(
                Path(temporary),
                git_runner=runner,
            ).advance(self.module.StartAudit(self.target(repo)))

            packet = packet_of(result)
            commands = [call[0] for call in runner.calls]
            self.assertEqual(
                sum(command[:2] == ("diff", "--name-status") for command in commands),
                1,
            )
            self.assertEqual(
                sum(command[:2] == ("archive", "--format=tar") for command in commands),
                1,
            )
            grep = [command for command in commands if command[:4] == (
                "grep", "-n", "-I", "-F"
            )]
            self.assertEqual(len(grep), 1)
            reuse = packet["evidence"]["reuse:SEARCH-1"]
            self.assertEqual(reuse["query"], sorted(reuse["query"]))
            self.assertLessEqual(len(reuse["query"]), 128)
            self.assertEqual(reuse["scope"], {
                "commit": packet["authority"]["head_sha"],
                "tree": "full",
            })
            self.assertEqual(
                [call[3] for call in runner.calls if call[0] == grep[0]],
                [2 * 1024 * 1024],
            )
            self.assertIn("validate_percentage", reuse["results"])

    def test_dirty_worktree_is_disclosed_but_recorded_head_is_authority(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            checkout = repo / "src/checkout.py"
            checkout.write_text(
                checkout.read_text(encoding="utf-8")
                + "\nDIRTY_WORKTREE_SENTINEL = True\n",
                encoding="utf-8",
            )

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(self.target(repo))
            )

            packet = packet_of(result)
            self.assertTrue(packet["worktree"]["dirty"])
            self.assertIn("src/checkout.py", packet["worktree"]["status"])
            self.assertNotIn(
                "DIRTY_WORKTREE_SENTINEL",
                json.dumps(packet, sort_keys=True),
            )

    def test_deadline_is_capped_and_stored_as_absolute_value(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            clock = FakeClock()
            result = self.runtime(
                Path(temporary),
                clock=clock,
            ).advance(
                self.module.StartAudit(
                    self.target(repo),
                    deadline_seconds=999,
                )
            )
            clock.value = 9000.0

            state = self.module.SessionStore(Path(temporary)).load(
                result.session
            )
            self.assertEqual(state["absolute_deadline"], 1300.0)
            self.assertEqual(packet_of(result)["deadline"]["absolute"], 1300.0)

    def test_generation_is_external_content_addressed_and_read_only(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            run_id, digest = result.session.split(".", 1)
            run = root / run_id
            generation = run / "generations" / digest

            self.assertFalse(result.response_path.exists())
            self.assertFalse(result.response_path.is_relative_to(repo))
            self.assertEqual(stat.S_IMODE(run.stat().st_mode), 0o700)
            state_bytes = (generation / "state.json").read_bytes()
            self.assertEqual(hashlib.sha256(state_bytes).hexdigest(), digest)
            for name in ("state.json", "manifest.json", "packet.json"):
                self.assertEqual(
                    stat.S_IMODE((generation / name).stat().st_mode),
                    0o400,
                )

    def test_wrong_generation_digest_or_manifest_is_rejected(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            store = self.module.SessionStore(root)
            run_id, digest = result.session.split(".", 1)
            with self.assertRaises(self.module.SessionIntegrityError):
                store.load(f"{run_id}.{'0' * 64}")

            manifest = root / run_id / "generations" / digest / "manifest.json"
            manifest.chmod(0o600)
            manifest.write_text("{}\n", encoding="utf-8")
            manifest.chmod(0o400)
            with self.assertRaises(self.module.SessionIntegrityError):
                store.load(result.session)

    def test_packet_cannot_be_rebound_by_rewriting_manifest(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            run_id, digest = result.session.split(".", 1)
            generation = root / run_id / "generations" / digest
            packet = generation / "packet.json"
            packet.chmod(0o600)
            packet.write_text("{}\n", encoding="utf-8")
            packet.chmod(0o400)
            manifest = generation / "manifest.json"
            manifest.chmod(0o600)
            manifest.write_text(
                json.dumps(
                    {
                        "packet_sha256": hashlib.sha256(
                            packet.read_bytes()
                        ).hexdigest(),
                        "schema_version": 1,
                        "state_sha256": digest,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest.chmod(0o400)

            with self.assertRaises(self.module.SessionIntegrityError):
                self.module.SessionStore(root).load(result.session)

    def test_authority_failure_preserves_report_and_creates_no_session(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            report.write_bytes(b"existing report bytes\n")
            approval = report.with_name("approval.json")
            approval.write_text("{}\n", encoding="utf-8")
            before = report.read_bytes()

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(self.target(repo))
            )

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "AUTHORITY_INVALID")
            self.assertEqual(report.read_bytes(), before)
            self.assertTrue(result.prior_report_preserved)
            self.assertTrue(result.zero_target_writes)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_deferred_transitions_stop_explicitly(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.runtime(Path(temporary))
            continued = runtime.advance(
                self.module.ContinueAudit("opaque", Path(temporary) / "r.json")
            )
            compound = runtime.advance(
                self.module.StartAudit(
                    self.module.AuditTarget(Path("/a"), "a", "A"),
                    then=self.module.AuditTarget(Path("/b"), "b", "B"),
                )
            )

            self.assertEqual(continued.code, "CONTINUE_UNAVAILABLE")
            self.assertEqual(compound.code, "COMPOUND_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
