import hashlib
import importlib
import io
import json
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from dataclasses import dataclass
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


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


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


@dataclass
class MutableLeaf:
    value: int


class MutableInt(int):
    pass


class MutableString(str):
    pass


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
                [
                    item["path"]
                    for item in packet["evidence"]["inventory:NAME-1"][
                        "entries"
                    ]
                ],
                ["src/checkout.py", "src/pricing.py", "tests/test_checkout.py"],
            )
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

    def test_deferred_old_side_of_rename_is_not_code_evidence(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            destination = repo / "src/plan_claim.py"
            git(repo, "mv", "plan.md", str(destination.relative_to(repo)))
            git(repo, "commit", "-m", "refactor: relocate implementation plan")

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(self.target(repo))
            )

            packet = packet_of(result)
            paths = [item["path"] for item in packet["changed_paths"]]
            self.assertNotIn("src/plan_claim.py", paths)
            self.assertNotIn("The design is settled", json.dumps(packet))

    def test_machine_grep_preserves_colon_and_newline_path_identity(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            colon = repo / "src/colon:name.py"
            newline = repo / "src/line\nname.py"
            narrative = repo / "claim:\nsummary.md"
            for path in (colon, newline, narrative):
                path.write_text(
                    "validate_percentage = 'PATH_SENTINEL'\n",
                    encoding="utf-8",
                )
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "test: add unusual git paths")

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(
                    self.target(repo, narrative_paths=(narrative,))
                )
            )

            records = packet_of(result)["evidence"]["reuse:SEARCH-1"][
                "results"
            ]
            self.assertEqual(
                {item["path"] for item in records if "PATH_SENTINEL" in item["text"]},
                {"src/colon:name.py", "src/line\nname.py"},
            )

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
            self.assertTrue(
                any(
                    "validate_percentage" in item["text"]
                    for item in reuse["results"]
                )
            )

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
            self.assertEqual(packet["worktree"]["status"], "dirty")
            self.assertNotIn(
                "DIRTY_WORKTREE_SENTINEL",
                json.dumps(packet, sort_keys=True),
            )

    def test_deadline_boundaries_have_no_hidden_minimum(self):
        expected_evidence = {1: 1001.0, 60: 1060.0, 61: 1001.0, 300: 1180.0}
        for seconds in (1, 60, 61, 300):
            with self.subTest(seconds=seconds), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                clock = FakeClock()
                result = self.runtime(
                    Path(temporary),
                    clock=clock,
                ).advance(
                    self.module.StartAudit(
                        self.target(repo),
                        deadline_seconds=seconds,
                    )
                )

                self.assertIsInstance(result, self.module.NeedJudgment)
                packet = packet_of(result)
                self.assertEqual(packet["deadline"]["absolute"], 1000 + seconds)
                self.assertEqual(
                    packet["deadline"]["evidence"],
                    expected_evidence[seconds],
                )

        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            result = self.runtime(
                Path(temporary),
                clock=FakeClock(),
            ).advance(
                self.module.StartAudit(
                    self.target(repo),
                    deadline_seconds=999,
                )
            )
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
            self.assertEqual(
                stat.S_IMODE((run / "key").stat().st_mode),
                0o400,
            )

    def test_append_rejects_an_existing_regular_response_file(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            store = self.module.SessionStore(root)
            state = store.load(first.session)
            state["nonce"] = "a" * 32
            state["response_name"] = f"{'b' * 32}.json"
            run_id = first.session.split(".", 1)[0]
            response = root / run_id / "inbox" / state["response_name"]
            response.write_bytes(b"pre-existing response\n")
            generations = root / run_id / "generations"
            before = {path.name for path in generations.iterdir()}

            with self.assertRaises(self.module.SessionIntegrityError):
                store.append(
                    first.session,
                    state,
                    {"schema_version": 1, "kind": "next"},
                )

            self.assertEqual(response.read_bytes(), b"pre-existing response\n")
            self.assertEqual(
                {path.name for path in generations.iterdir()},
                before,
            )

    def test_append_rejects_a_response_name_used_by_its_predecessor(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            store = self.module.SessionStore(root)
            state = store.load(first.session)
            state["nonce"] = "a" * 32
            run_id = first.session.split(".", 1)[0]
            generations = root / run_id / "generations"
            before = {path.name for path in generations.iterdir()}

            with self.assertRaises(self.module.SessionIntegrityError):
                store.append(
                    first.session,
                    state,
                    {"schema_version": 1, "kind": "next"},
                )

            self.assertEqual(
                {path.name for path in generations.iterdir()},
                before,
            )

    def test_append_rejects_a_response_symlink_without_touching_its_target(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            store = self.module.SessionStore(root)
            state = store.load(first.session)
            state["nonce"] = "a" * 32
            state["response_name"] = f"{'b' * 32}.json"
            run_id = first.session.split(".", 1)[0]
            target = repo / "response-target.json"
            target.write_bytes(b"target sentinel\n")
            response = root / run_id / "inbox" / state["response_name"]
            response.symlink_to(target)
            generations = root / run_id / "generations"
            before = {path.name for path in generations.iterdir()}

            with self.assertRaises(self.module.SessionIntegrityError):
                store.append(
                    first.session,
                    state,
                    {"schema_version": 1, "kind": "next"},
                )

            self.assertTrue(response.is_symlink())
            self.assertEqual(target.read_bytes(), b"target sentinel\n")
            self.assertEqual(
                {path.name for path in generations.iterdir()},
                before,
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

    def test_unkeyed_coordinated_generation_is_not_an_issued_session(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            run_id, prior_digest = result.session.split(".", 1)
            packet = {"schema_version": 1, "kind": "forged"}
            packet_bytes = canonical(packet)
            state = {
                "schema_version": 1,
                "phase": "code",
                "target": "primary",
                "absolute_deadline": 1300.0,
                "nonce": "1" * 32,
                "response_name": f"{'2' * 32}.json",
                "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            }
            state_bytes = canonical(state)
            digest = hashlib.sha256(state_bytes).hexdigest()
            generation = (
                root / run_id / "generations" / digest
            )
            generation.mkdir()
            (generation / "state.json").write_bytes(state_bytes)
            (generation / "packet.json").write_bytes(packet_bytes)
            (generation / "manifest.json").write_bytes(
                canonical(
                    {
                        "schema_version": 1,
                        "state_sha256": digest,
                        "packet_sha256": hashlib.sha256(
                            packet_bytes
                        ).hexdigest(),
                    }
                )
            )
            for path in generation.iterdir():
                path.chmod(0o400)

            with self.assertRaises(self.module.SessionIntegrityError):
                self.module.SessionStore(root).load(f"{run_id}.{digest}")
            self.assertNotEqual(prior_digest, digest)

    def test_appended_generation_is_hmac_chained_to_its_predecessor(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            store = self.module.SessionStore(root)
            state = store.load(first.session)
            state["nonce"] = "a" * 32
            state["response_name"] = f"{'b' * 32}.json"
            second = store.append(
                first.session,
                state,
                {"schema_version": 1, "kind": "next"},
            )
            run_id, first_digest = first.session.split(".", 1)
            _, second_digest = second.token.split(".", 1)
            manifest = json.loads(
                (
                    root
                    / run_id
                    / "generations"
                    / second_digest
                    / "manifest.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(
                manifest["previous_generation_sha256"],
                first_digest,
            )
            self.assertRegex(manifest["hmac_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(store.load(second.token)["nonce"], "a" * 32)
            self.assertEqual(store.load(first.session)["phase"], "code")

    def test_session_trust_and_response_consumption_boundaries_are_explicit(self):
        session_doc = sys.modules["audit_session"].__doc__

        self.assertIn("same effective user", session_doc)
        self.assertIn("does not protect", session_doc)
        self.assertIn("exact issued response name", session_doc)
        self.assertIn("O_NOFOLLOW", session_doc)

    def test_session_rejects_replaced_internal_directories(self):
        for component, operation in (
            ("generations", "load"),
            ("claims", "claim"),
            ("inbox", "load"),
        ):
            with self.subTest(component=component), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result = self.runtime(root).advance(
                    self.module.StartAudit(self.target(repo))
                )
                run_id = result.session.split(".", 1)[0]
                run = root / run_id
                outside = root / f"outside-{component}"
                (run / component).rename(outside)
                (run / component).symlink_to(
                    outside,
                    target_is_directory=True,
                )
                store = self.module.SessionStore(root)

                with self.assertRaises(self.module.SessionIntegrityError):
                    getattr(store, operation)(result.session)
                if component == "claims":
                    self.assertEqual(list(outside.iterdir()), [])

    def test_state_retains_private_freshness_guards(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            narrative = repo / "review-summary.md"
            narrative.write_bytes(b"opaque narrative bytes\n")
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            report.write_bytes(b"opaque report bytes\n")
            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(
                    self.target(repo, narrative_paths=(narrative,))
                )
            )
            state = self.module.SessionStore(Path(temporary)).load(
                result.session
            )
            packet = packet_of(result)

            self.assertEqual(
                state["target_identity"],
                {
                    "repository_root": str(repo.resolve()),
                    "branch": "feature/proj-123",
                    "ticket": "PROJ-123",
                },
            )
            for key in (
                "repository_root",
                "branch_directory",
                "selected_root",
                "current_sha256",
                "approval_path",
                "approval_sha256",
                "contract_path",
                "contract_sha256",
                "ledger_path",
                "ledger_present",
                "base_sha",
                "head_sha",
            ):
                self.assertIn(key, state["authority_guard"])
            self.assertEqual(
                state["ledger_guard"]["sha256"],
                hashlib.sha256(
                    Path(state["authority_guard"]["ledger_path"]).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                state["report_guard"]["sha256"],
                hashlib.sha256(b"opaque report bytes\n").hexdigest(),
            )
            self.assertEqual(
                state["narrative_guards"][0]["sha256"],
                hashlib.sha256(
                    (repo / state["narrative_guards"][0]["path"]).read_bytes()
                ).hexdigest(),
            )
            self.assertIn("plan.md", state["deferred_narrative_paths"])
            self.assertIn(
                str(narrative.resolve()),
                {
                    item["path"]
                    for item in state["narrative_guards"]
                },
            )
            self.assertEqual(
                {
                    item["path"]: item["sha256"]
                    for item in state["narrative_guards"]
                }[str(narrative.resolve())],
                hashlib.sha256(b"opaque narrative bytes\n").hexdigest(),
            )
            self.assertIn("initial_status_sha256", state)
            self.assertIn("source_guards", state)
            self.assertNotIn(str(repo.resolve()), json.dumps(packet))
            self.assertNotIn("review-summary.md", json.dumps(packet))

    def test_changed_symlink_is_captured_as_link_target_bytes(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            link = repo / "src" / "price-link.py"
            link.symlink_to("pricing.py")
            git(repo, "add", str(link.relative_to(repo)))
            git(repo, "commit", "-m", "feat: add price module link")

            result = self.runtime(Path(temporary)).advance(
                self.module.StartAudit(self.target(repo))
            )
            packet = packet_of(result)
            state = self.module.SessionStore(Path(temporary)).load(
                result.session
            )
            changed = {
                item["path"]: item for item in packet["changed_paths"]
            }

            self.assertEqual(
                changed["src/price-link.py"]["head_blob"],
                {
                    "type": "symlink",
                    "target": {
                        "encoding": "utf-8",
                        "content": "pricing.py",
                    },
                },
            )
            self.assertEqual(
                state["source_guards"]["head_blob_sha256"][
                    "src/price-link.py"
                ],
                hashlib.sha256(b"pricing.py").hexdigest(),
            )

    def test_recorded_head_rejects_unsupported_entry_types(self):
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w:") as archive:
            entry = tarfile.TarInfo("src/device")
            entry.type = tarfile.FIFOTYPE
            archive.addfile(entry)

        with self.assertRaisesRegex(
            self.module.EvidenceError,
            "unsupported recorded-HEAD Git entry type",
        ):
            sys.modules["audit_evidence"]._archive_blobs(
                archive_bytes.getvalue(),
                ["src/device"],
            )

    def test_contract_buffer_must_match_resolved_authority_digest(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            def replace_after_resolution(path, branch, ticket):
                authority = self.module.resolve_authority(path, branch, ticket)
                contract = Path(authority["contract_path"])
                contract.write_bytes(
                    contract.read_bytes().replace(
                        b"without adding new structure",
                        b"with unapproved replacement text",
                    )
                )
                return authority

            result = self.runtime(
                Path(temporary),
                authority_resolver=replace_after_resolution,
            ).advance(self.module.StartAudit(self.target(repo)))

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "CONTRACT_INVALID")

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

    def test_unavailable_continue_does_not_claim_a_valid_generation(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.runtime(root).advance(
                self.module.StartAudit(self.target(repo))
            )
            runtime = self.runtime(root)
            stopped = runtime.advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            store = self.module.SessionStore(root)

            self.assertEqual(stopped.code, "CONTINUE_UNAVAILABLE")
            store.claim(started.session)

    def test_public_envelope_mappings_are_recursively_immutable(self):
        closed = {"nested": {"values": [1, 2]}}
        attestation = {"nested": {"values": [3, 4]}}
        judgment = self.module.NeedJudgment(
            session="s",
            target="primary",
            kind="code",
            packet_path=Path("/packet"),
            packet_sha256="a" * 64,
            response_path=Path("/response"),
            next_command=("continue",),
            nonce="b" * 32,
            closed_target=closed,
        )
        complete = self.module.AuditComplete(
            verdict="PASS",
            route=("qa-ticket",),
            report_path=Path("/report"),
            report_sha256="c" * 64,
            mutation_attestation=attestation,
        )
        closed["nested"]["values"].append(9)
        attestation["nested"]["values"].append(9)

        self.assertEqual(
            judgment.closed_target["nested"]["values"],
            (1, 2),
        )
        self.assertEqual(
            complete.mutation_attestation["nested"]["values"],
            (3, 4),
        )
        with self.assertRaises(TypeError):
            judgment.closed_target["new"] = "value"

    def test_public_envelopes_accept_only_immutable_json_like_leaves(self):
        accepted = self.module.NeedJudgment(
            session="s",
            target="primary",
            kind="code",
            packet_path=Path("/packet"),
            packet_sha256="a" * 64,
            response_path=Path("/response"),
            next_command=("continue",),
            nonce="b" * 32,
            closed_target={
                "none": None,
                "bool": True,
                "int": 1,
                "float": 1.25,
                "str": "value",
                "sequence": [False, 2],
            },
        )
        self.assertEqual(accepted.closed_target["float"], 1.25)

        unsupported = (
            bytearray(b"mutable"),
            MutableLeaf(1),
            object(),
            float("inf"),
            float("-inf"),
            float("nan"),
            b"bytes",
            {"set"},
            Path("/mutable-or-domain-object"),
            MutableInt(1),
            MutableString("value"),
        )
        for leaf in unsupported:
            with self.subTest(leaf=type(leaf).__name__), self.assertRaises(
                TypeError
            ):
                self.module.NeedJudgment(
                    session="s",
                    target="primary",
                    kind="code",
                    packet_path=Path("/packet"),
                    packet_sha256="a" * 64,
                    response_path=Path("/response"),
                    next_command=("continue",),
                    nonce="b" * 32,
                    closed_target={"leaf": leaf},
                )

        with self.assertRaises(TypeError):
            self.module.AuditComplete(
                verdict="PASS",
                route=("qa-ticket",),
                report_path=Path("/report"),
                report_sha256="c" * 64,
                mutation_attestation={1: "non-string key"},
            )


if __name__ == "__main__":
    unittest.main()
