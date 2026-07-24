import hashlib
import ctypes
import fcntl
import errno
import gc
import importlib
import json
import multiprocessing
import os
import signal
import stat
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_start import FakeClock, git


ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "check-contract" / "scripts"
RESPONSE_LIMIT = 2 * 1024 * 1024


def load_modules():
    sys.path.insert(0, str(SCRIPTS))
    try:
        for name in (
            "audit_runtime",
            "audit_reconciliation",
            "audit_session",
        ):
            sys.modules.pop(name, None)
        runtime = importlib.import_module("audit_runtime")
        reconciliation = importlib.import_module("audit_reconciliation")
        return runtime, reconciliation
    finally:
        sys.path.pop(0)


def valid_code_judgment(packet):
    clauses = {}
    for clause_id in packet["clause_ids"]:
        family = clause_id.split("-", 1)[0][0]
        namespace = {
            "O": "behavior",
            "B": "behavior",
            "N": "risk",
            "I": "risk",
            "C": "public-contract",
            "R": "reuse",
            "S": "surface",
            "K": "complexity",
            "A": "acceptance",
        }[family]
        clauses[clause_id] = {
            "status": "MET",
            "evidence_ids": [f"{namespace}:{clause_id}"],
            "reason": f"{clause_id} is evidenced by recorded code.",
            "contract_boundary_changed": False,
        }
    paths = {}
    for path_id in packet["changed_path_ids"]:
        paths[path_id] = {
            "surface": {
                "status": "MET",
                "evidence_ids": ["source:CAPTURE-1"],
                "reason": "The recorded path implements the expected surface.",
            },
            "yagni_items": [],
            "reuse_items": [
                {
                    "kind": "NO_REUSE_AVAILABLE",
                    "evidence_ids": ["reuse:SEARCH-1"],
                    "reason": "The full-tree search found no compatible helper.",
                }
            ],
        }
    return {
        "clauses": clauses,
        "path_assessments": paths,
        "deviations": [],
    }


def code_response(started, judgment=None, **overrides):
    value = {
        "schema_version": 1,
        "session": started.session,
        "nonce": started.nonce,
        "packet_sha256": started.packet_sha256,
        "kind": "code",
        "judgment": judgment
        if judgment is not None
        else valid_code_judgment(packet_of(started)),
    }
    value.update(overrides)
    return value


def write_response(path, value):
    Path(path).write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


class TruncatedReuseRunner:
    def __init__(self, module):
        self.module = module
        self.delegate = module.LocalGitRunner()

    def run(self, args, *, cwd, deadline, output_limit=None):
        result = self.delegate.run(
            args,
            cwd=cwd,
            deadline=deadline,
            output_limit=output_limit,
        )
        if args[:1] == ["grep"]:
            return type(result)(
                result.stdout,
                True,
                result.timed_out,
            )
        return result


class AmbiguousShaRunner:
    def __init__(self, module, head):
        self.module = module
        self.head = head
        self.delegate = module.LocalGitRunner()
        self.result_type = sys.modules["audit_evidence"].CommandResult
        self.disambiguations = []

    def run(self, args, *, cwd, deadline, output_limit=None):
        if args[:1] == ["rev-parse"] and args[1].startswith(
            "--disambiguate="
        ):
            prefix = args[1].partition("=")[2]
            self.disambiguations.append(prefix)
            other = prefix + "f" * (40 - len(prefix))
            return self.result_type(
                f"{self.head}\n{other}\n".encode("ascii"),
                False,
                False,
            )
        return self.delegate.run(
            args,
            cwd=cwd,
            deadline=deadline,
            output_limit=output_limit,
        )


class DeadlineAdvancingRunner:
    def __init__(self, module, clock):
        self.delegate = module.LocalGitRunner(clock)
        self.clock = clock

    def run(self, args, *, cwd, deadline, output_limit=None):
        result = self.delegate.run(
            args,
            cwd=cwd,
            deadline=deadline,
            output_limit=output_limit,
        )
        if args[:1] == ["rev-parse"] and args[1].startswith(
            "--disambiguate="
        ):
            self.clock.value = deadline + 0.001
        return result


class FailingQaResolutionRunner:
    def __init__(self, module):
        self.module = module
        self.delegate = module.LocalGitRunner()

    def run(self, args, *, cwd, deadline, output_limit=None):
        if args[:1] == ["rev-parse"] and args[1].startswith(
            "--disambiguate="
        ):
            raise self.module.EvidenceError(
                "injected QA reference resolution failure"
            )
        return self.delegate.run(
            args,
            cwd=cwd,
            deadline=deadline,
            output_limit=output_limit,
        )


class AuditRuntimeReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, cls.reconciliation = load_modules()

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

    def start(self, repo, root, **target_overrides):
        result = self.runtime(root).advance(
            self.module.StartAudit(self.target(repo, **target_overrides))
        )
        self.assertIsInstance(result, self.module.NeedJudgment)
        return result

    def generation_count(self, root, token):
        run = token.split(".", 1)[0]
        return sum(
            not path.name.startswith(".")
            for path in (Path(root) / run / "generations").iterdir()
        )

    def test_valid_code_response_issues_guarded_reconciliation_packet(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            summary = repo / ".worker-results/implementation-summary.md"
            qa = repo / "review-evidence.md"
            report.write_text("PRIOR REPORT SENTINEL\n", encoding="utf-8")
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_text(
                "IMPLEMENTATION SUMMARY SENTINEL\n",
                encoding="utf-8",
            )
            git(repo, "add", str(summary.relative_to(repo)))
            git(repo, "commit", "-m", "docs: record implementation summary")
            head = git(repo, "rev-parse", "HEAD")
            qa.write_text(
                "<!-- qa-pr-evidence -->\n"
                "## QA evidence — ✅ PASS "
                f"<sub>(@ {head[:12]})</sub>\n"
                "QA NARRATIVE SENTINEL\n",
                encoding="utf-8",
            )
            root = Path(temporary)
            started = self.start(
                repo,
                root,
                narrative_paths=(qa,),
            )
            write_response(started.response_path, code_response(started))

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertIsInstance(result, self.module.NeedJudgment)
            self.assertEqual(result.kind, "reconciliation")
            packet = packet_of(result)
            code_packet = packet_of(started)
            serialized = json.dumps(packet, sort_keys=True)
            self.assertEqual(packet["kind"], "reconciliation")
            self.assertEqual(packet["authority"], code_packet["authority"])
            self.assertEqual(packet["clauses"], code_packet["clauses"])
            self.assertEqual(packet["clause_ids"], code_packet["clause_ids"])
            self.assertEqual(
                [
                    item["clause_id"]
                    for item in packet["code_judgment"]["clauses"]
                ],
                code_packet["clause_ids"],
            )
            self.assertTrue(packet["acceptance_qa_exists"])
            self.assertEqual(
                [entry["ledger_id"] for entry in packet["ledger_entries"]],
                ["D1"],
            )
            self.assertEqual(packet["probe_ids"], ["Q1"])
            self.assertEqual(packet["deviation_ids"], [])
            self.assertIn("PRIOR REPORT SENTINEL", serialized)
            self.assertIn("IMPLEMENTATION SUMMARY SENTINEL", serialized)
            self.assertIn("QA NARRATIVE SENTINEL", serialized)
            self.assertNotIn('"argv"', serialized)
            self.assertNotIn('"shell"', serialized)
            self.assertNotIn('"module": "src.pricing"', serialized)
            response_properties = packet["response_schema"]["properties"][
                "judgment"
            ]["properties"]
            self.assertEqual(
                set(response_properties),
                {
                    "ledger_entries",
                    "deviation_matches",
                    "contract_obsolete",
                    "probe_id",
                },
            )
            ledger_schema = response_properties["ledger_entries"]
            self.assertEqual(ledger_schema["type"], "object")
            self.assertEqual(ledger_schema["required"], ["D1"])
            self.assertFalse(ledger_schema["additionalProperties"])
            self.assertEqual(
                set(ledger_schema["properties"]["D1"]["properties"]),
                {"status", "evidence_ids", "reason"},
            )
            self.assertNotIn("selected_probe_id", response_properties)
            self.assertNotIn("acceptance_qa_exists", response_properties)
            self.assertIn("evidence_ids", json.dumps(response_properties))
            issued = packet["evidence_ids"]
            self.assertEqual(
                response_properties["contract_obsolete"]["properties"][
                    "evidence_ids"
                ]["items"]["enum"],
                issued,
            )
            self.assertIn("contract:O1", issued)
            self.assertIn("code:O1", issued)
            self.assertTrue(
                any(item.startswith("code-path:") for item in issued)
            )
            self.assertEqual(
                response_properties["contract_obsolete"]["properties"][
                    "evidence_ids"
                ]["minItems"],
                0,
            )
            obsolete_condition = packet["response_schema"]["properties"][
                "judgment"
            ]["allOf"][0]
            self.assertEqual(
                obsolete_condition["if"]["properties"][
                    "contract_obsolete"
                ]["properties"]["value"],
                {"const": True},
            )
            self.assertEqual(
                obsolete_condition["then"]["properties"][
                    "contract_obsolete"
                ]["properties"]["evidence_ids"]["minItems"],
                1,
            )
            state = self.module.SessionStore(root).load(result.session)
            self.assertEqual(state["phase"], "reconciliation")
            self.assertEqual(
                state["code_judgment"]["clauses"][0]["clause_id"],
                packet_of(started)["clause_ids"][0],
            )
            self.assertEqual(
                state["issued_probes"]["Q1"]["kind"],
                "python-call-v1",
            )

    def test_reuse_truncation_is_runtime_owned_reconciliation_evidence(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.runtime(
                root,
                git_runner=TruncatedReuseRunner(self.module),
            ).advance(
                self.module.StartAudit(self.target(repo))
            )
            packet = packet_of(started)
            self.assertTrue(packet["reuse_coverage_indeterminate"])
            write_response(started.response_path, code_response(started))

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            reconciliation = packet_of(result)
            self.assertIn(
                "reuse_coverage_indeterminate",
                reconciliation["runtime_facts"],
            )
            self.assertTrue(
                reconciliation["runtime_facts"][
                    "reuse_coverage_indeterminate"
                ],
            )
            state = self.module.SessionStore(root).load(result.session)
            self.assertTrue(state["reuse_coverage_indeterminate"])
            self.assertEqual(
                reconciliation["runtime_facts"]["reuse_evidence_id"],
                "runtime:REUSE-COVERAGE-1",
            )

    def test_invalid_envelopes_claim_once_and_append_terminal_generation(self):
        mutations = {
            "schema-version": lambda value: {
                **value,
                "schema_version": 2,
            },
            "extra": lambda value: {**value, "extra": True},
            "missing": lambda value: {
                key: item for key, item in value.items() if key != "nonce"
            },
            "session": lambda value: {**value, "session": "0" * 97},
            "kind": lambda value: {**value, "kind": "reconciliation"},
            "packet": lambda value: {
                **value,
                "packet_sha256": "0" * 64,
            },
            "nonce": lambda value: {**value, "nonce": "0" * 32},
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                started = self.start(repo, root)
                write_response(
                    started.response_path,
                    mutate(code_response(started)),
                )

                result = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        started.session,
                        started.response_path,
                    )
                )

                self.assertIsInstance(result, self.module.AuditStopped)
                self.assertEqual(result.code, "RESPONSE_INVALID")
                self.assertEqual(self.generation_count(root, started.session), 2)
                duplicate = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        started.session,
                        started.response_path,
                    )
                )
                self.assertIsInstance(duplicate, self.module.AuditStopped)
                self.assertEqual(
                    self.generation_count(root, started.session),
                    2,
                )

    def test_duplicate_json_keys_are_terminal_even_when_last_value_matches(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            valid = json.dumps(
                code_response(started),
                sort_keys=True,
                separators=(",", ":"),
            )
            duplicated = valid.replace(
                '"nonce":',
                f'"nonce":"{"0" * 32}","nonce":',
                1,
            )
            started.response_path.write_text(
                duplicated + "\n",
                encoding="utf-8",
            )

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "RESPONSE_INVALID")

    def test_invalid_json_missing_file_wrong_path_symlink_and_oversize_are_terminal(self):
        cases = ("invalid-json", "missing", "wrong-path", "symlink", "oversize")
        for name in cases:
            with self.subTest(name=name), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                started = self.start(repo, root)
                caller_path = started.response_path
                if name == "invalid-json":
                    started.response_path.write_bytes(b"{")
                elif name == "wrong-path":
                    write_response(started.response_path, code_response(started))
                    caller_path = started.response_path.with_name("other.json")
                elif name == "symlink":
                    outside = root / "outside.json"
                    write_response(outside, code_response(started))
                    started.response_path.symlink_to(outside)
                elif name == "oversize":
                    started.response_path.write_bytes(
                        b" " * (RESPONSE_LIMIT + 1)
                    )

                result = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        started.session,
                        caller_path,
                    )
                )

                self.assertIsInstance(result, self.module.AuditStopped)
                self.assertEqual(self.generation_count(root, started.session), 2)

        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            started.response_path.write_text("[]\n", encoding="utf-8")
            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            self.assertEqual(result.code, "RESPONSE_INVALID")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_fifo_response_is_nonblocking_claimed_and_terminal(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            os.mkfifo(started.response_path)

            before = time.monotonic()
            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            elapsed = time.monotonic() - before

            self.assertLess(elapsed, 1.0)
            self.assertEqual(result.code, "RESPONSE_INVALID")
            self.assertEqual(self.generation_count(root, started.session), 2)
            duplicate = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            self.assertIsInstance(duplicate, self.module.AuditStopped)
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_response_at_exact_byte_limit_is_accepted(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            raw = (
                json.dumps(
                    code_response(started),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            self.assertLess(len(raw), RESPONSE_LIMIT)
            started.response_path.write_bytes(
                raw + b" " * (RESPONSE_LIMIT - len(raw))
            )

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertIsInstance(result, self.module.NeedJudgment)

    def test_invalid_inner_judgment_precedes_all_narrative_reads(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            narrative = repo / "review-summary.md"
            narrative.write_text("ORIGINAL\n", encoding="utf-8")
            root = Path(temporary)
            started = self.start(
                repo,
                root,
                narrative_paths=(narrative,),
            )
            narrative.write_text("MUTATED AFTER START\n", encoding="utf-8")
            write_response(
                started.response_path,
                code_response(started, judgment={}),
            )

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertEqual(result.code, "RESPONSE_INVALID")
            self.assertNotIn("narrative", result.reason.lower())

    def test_valid_inner_judgment_rejects_changed_guarded_narrative(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            narrative = repo / "review-summary.md"
            narrative.write_text("ORIGINAL\n", encoding="utf-8")
            root = Path(temporary)
            started = self.start(
                repo,
                root,
                narrative_paths=(narrative,),
            )
            narrative.write_text("MUTATED AFTER START\n", encoding="utf-8")
            write_response(started.response_path, code_response(started))

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertEqual(result.code, "NARRATIVE_INVALID")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_regular_narrative_replaced_by_fifo_stops_without_blocking(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            narrative = repo / "review-summary.md"
            narrative.write_text("ORIGINAL\n", encoding="utf-8")
            root = Path(temporary)
            started = self.start(
                repo,
                root,
                narrative_paths=(narrative,),
            )
            narrative.unlink()
            os.mkfifo(narrative)
            write_response(started.response_path, code_response(started))

            before = time.monotonic()
            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            elapsed = time.monotonic() - before

            self.assertLess(elapsed, 1.0)
            self.assertEqual(result.code, "NARRATIVE_INVALID")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_start_never_reads_ledger_report_or_narrative_bytes(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            narrative = repo / "review-summary.md"
            summary = repo / ".worker-results/implementation-summary.md"
            report.write_text("PRIOR BYTES\n", encoding="utf-8")
            narrative.write_text("NARRATIVE BYTES\n", encoding="utf-8")
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_text("SUMMARY BYTES\n", encoding="utf-8")
            git(repo, "add", str(summary.relative_to(repo)))
            git(repo, "commit", "-m", "docs: add deferred summary")
            ledger = (
                repo
                / ".notes/feature-proj-123/contract/v1/execution-ledger.md"
            )
            forbidden = {
                str(path.absolute())
                for path in (ledger, report, narrative, summary)
            }
            original = Path.read_bytes

            def selective_read(path):
                if str(path.absolute()) in forbidden:
                    raise AssertionError(
                        f"narrative bytes read before code judgment: {path}"
                    )
                return original(path)

            with mock.patch.object(Path, "read_bytes", selective_read):
                started = self.start(
                    repo,
                    Path(temporary),
                    narrative_paths=(narrative,),
                )

            state = self.module.SessionStore(Path(temporary)).load(
                started.session
            )
            for guard in (
                state["ledger_guard"],
                state["report_guard"],
                *state["narrative_guards"],
            ):
                self.assertNotIn("sha256", guard)
                self.assertIn("mtime_ns", guard)

            write_response(started.response_path, code_response(started))
            result = self.runtime(Path(temporary)).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            next_state = self.module.SessionStore(Path(temporary)).load(
                result.session
            )
            content_guards = next_state["narrative_content_guards"]
            self.assertRegex(
                content_guards["ledger"]["sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertEqual(
                content_guards["report"]["sha256"],
                hashlib.sha256(b"PRIOR BYTES\n").hexdigest(),
            )
            self.assertEqual(
                {
                    Path(item["path"]).name: item["sha256"]
                    for item in content_guards["narratives"]
                }["review-summary.md"],
                hashlib.sha256(b"NARRATIVE BYTES\n").hexdigest(),
            )
            self.assertEqual(
                {
                    Path(item["path"]).name: item["sha256"]
                    for item in content_guards["narratives"]
                }["implementation-summary.md"],
                hashlib.sha256(b"SUMMARY BYTES\n").hexdigest(),
            )

    def test_changed_ledger_and_prior_report_each_fail_guarded_read(self):
        for source in ("ledger", "report"):
            with self.subTest(source=source), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report = (
                    repo
                    / ".notes/feature-proj-123/contract/v1/check-report.md"
                )
                report.write_text("PRIOR\n", encoding="utf-8")
                started = self.start(repo, root)
                state = self.module.SessionStore(root).load(started.session)
                path = Path(
                    state[
                        "ledger_guard" if source == "ledger" else "report_guard"
                    ]["path"]
                )
                before = report.read_bytes()
                path.write_bytes(path.read_bytes() + b"MUTATED\n")
                write_response(started.response_path, code_response(started))

                result = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        started.session,
                        started.response_path,
                    )
                )

                self.assertEqual(result.code, "NARRATIVE_INVALID")
                if source == "ledger":
                    self.assertEqual(report.read_bytes(), before)

    def test_expired_response_is_claimed_and_terminal(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            clock = FakeClock()
            root = Path(temporary)
            started = self.runtime(root, clock=clock).advance(
                self.module.StartAudit(
                    self.target(repo),
                    deadline_seconds=60,
                )
            )
            write_response(started.response_path, code_response(started))
            clock.value = 1060.001

            result = self.runtime(root, clock=clock).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertEqual(result.code, "DEADLINE_EXPIRED")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_stale_code_generation_cannot_be_replayed(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            write_response(started.response_path, code_response(started))
            next_generation = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            count = self.generation_count(root, started.session)

            stale = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertIsInstance(next_generation, self.module.NeedJudgment)
            self.assertIsInstance(stale, self.module.AuditStopped)
            self.assertEqual(self.generation_count(root, started.session), count)

    def test_claimed_generation_can_have_only_one_successor(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            original_state = store.load(started.session)
            write_response(started.response_path, code_response(started))
            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            count = self.generation_count(root, started.session)
            duplicate_state = {
                **original_state,
                "phase": "terminal",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }

            with self.assertRaises(self.module.SessionIntegrityError):
                store.tombstone_claimed(
                    started.session,
                    duplicate_state,
                )

            self.assertIsInstance(result, self.module.NeedJudgment)
            self.assertEqual(self.generation_count(root, started.session), count)

    def test_precommit_append_failure_leaves_tombstone_recoverable(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            store.claim(started.session)
            original_state = store.load(started.session)
            next_state = {
                **original_state,
                "phase": "reconciliation",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }
            original_write = store._write_generation

            def fail_before_commit(*args, **kwargs):
                raise OSError("injected append failure")

            store._write_generation = fail_before_commit
            with self.assertRaises(OSError):
                store.append_claimed(
                    started.session,
                    next_state,
                    {"schema_version": 1, "kind": "reconciliation"},
                )
            store._write_generation = original_write
            terminal_state = {
                **original_state,
                "phase": "terminal",
                "nonce": "c" * 32,
                "response_name": f"{'d' * 32}.json",
            }

            terminal = store.tombstone_claimed(
                started.session,
                terminal_state,
            )

            self.assertEqual(packet_of(terminal)["kind"], "terminal")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_postcommit_append_error_recovers_authenticated_successor(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            store.claim(started.session)
            original_state = store.load(started.session)
            next_state = {
                **original_state,
                "phase": "reconciliation",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }
            original_write = store._write_generation

            def fail_after_commit(*args, **kwargs):
                original_write(*args, **kwargs)
                raise OSError("injected post-commit failure")

            store._write_generation = fail_after_commit
            result = store.append_claimed(
                started.session,
                next_state,
                {"schema_version": 1, "kind": "reconciliation"},
            )

            self.assertEqual(packet_of(result)["kind"], "reconciliation")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_competing_appenders_commit_one_authenticated_successor(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            self.module.SessionStore(root).claim(started.session)
            original_state = self.module.SessionStore(root).load(
                started.session
            )

            def append(suffix):
                state = {
                    **original_state,
                    "phase": "reconciliation",
                    "nonce": suffix * 32,
                    "response_name": f"{suffix * 32}.json",
                }
                try:
                    result = self.module.SessionStore(root).append_claimed(
                        started.session,
                        state,
                        {"schema_version": 1, "kind": "reconciliation"},
                    )
                    return ("ok", result.token)
                except self.module.SessionIntegrityError as error:
                    return ("error", str(error))

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(append, ("a", "b")))

            self.assertEqual(
                sorted(item[0] for item in outcomes),
                ["error", "ok"],
            )
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_shared_lease_appenders_are_linearized_before_commit(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            original_state = store.load(started.session)
            original_successors = store._direct_successors
            precheck_barrier = threading.Barrier(2)

            def synchronized_precheck(run_id, predecessor_digest):
                children = original_successors(run_id, predecessor_digest)
                if not children:
                    try:
                        precheck_barrier.wait(timeout=0.25)
                    except threading.BrokenBarrierError:
                        pass
                return children

            store._direct_successors = synchronized_precheck

            def append(suffix):
                state = {
                    **original_state,
                    "phase": "reconciliation",
                    "nonce": suffix * 32,
                    "response_name": f"{suffix * 32}.json",
                }
                try:
                    result = store.append_claimed(
                        started.session,
                        state,
                        {"schema_version": 1, "kind": "reconciliation"},
                        lease=lease,
                    )
                    return ("ok", result.token)
                except self.module.SessionIntegrityError as error:
                    return ("error", str(error))

            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    outcomes = list(executor.map(append, ("a", "b")))
            finally:
                store._direct_successors = original_successors
                lease.close()

            self.assertEqual(
                sorted(item[0] for item in outcomes),
                ["error", "ok"],
            )
            self.assertEqual(self.generation_count(root, started.session), 2)
            run_id, digest = started.session.split(".", 1)
            self.assertEqual(
                len(original_successors(run_id, digest)),
                1,
            )

    def test_forged_run_directory_lease_cannot_append_without_claim(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            original_state = store.load(started.session)
            run_id, digest = started.session.split(".", 1)
            descriptor = os.open(
                root / run_id,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
            )
            session_module = sys.modules["audit_session"]
            forged = session_module.ClaimLease(
                store,
                run_id,
                digest,
                descriptor,
            )
            next_state = {
                **original_state,
                "phase": "reconciliation",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }

            try:
                with self.assertRaises(self.module.SessionIntegrityError):
                    store.append_claimed(
                        started.session,
                        next_state,
                        {"schema_version": 1, "kind": "reconciliation"},
                        lease=forged,
                    )
            finally:
                forged.close()

            self.assertFalse(
                (root / run_id / "claims" / digest).exists()
            )
            self.assertEqual(self.generation_count(root, started.session), 1)

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_fork_inherited_lease_cannot_commit_a_second_successor(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            original_state = store.load(started.session)
            original_successors = store._direct_successors
            precheck = multiprocessing.Barrier(2, timeout=0.4)

            def synchronized_precheck(run_id, predecessor_digest):
                children = original_successors(run_id, predecessor_digest)
                if not children:
                    try:
                        precheck.wait()
                    except threading.BrokenBarrierError:
                        pass
                return children

            store._direct_successors = synchronized_precheck
            read_result, write_result = os.pipe()
            child = os.fork()
            if child == 0:
                os.close(read_result)
                state = {
                    **original_state,
                    "phase": "reconciliation",
                    "nonce": "b" * 32,
                    "response_name": f"{'c' * 32}.json",
                }
                try:
                    store.append_claimed(
                        started.session,
                        state,
                        {"schema_version": 1, "kind": "reconciliation"},
                        lease=lease,
                    )
                    outcome = b"child-ok"
                except Exception as error:
                    outcome = f"child-error:{type(error).__name__}".encode()
                os.write(write_result, outcome)
                os.close(write_result)
                os._exit(0)

            os.close(write_result)
            parent_state = {
                **original_state,
                "phase": "reconciliation",
                "nonce": "a" * 32,
                "response_name": f"{'d' * 32}.json",
            }
            try:
                try:
                    parent_result = store.append_claimed(
                        started.session,
                        parent_state,
                        {"schema_version": 1, "kind": "reconciliation"},
                        lease=lease,
                    )
                except Exception as error:
                    parent_result = error
            finally:
                store._direct_successors = original_successors
                lease.close()
            _, status = os.waitpid(child, 0)
            child_result = os.read(read_result, 1024)
            os.close(read_result)

            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
            self.assertIsInstance(
                parent_result,
                sys.modules["audit_session"].SessionGeneration,
            )
            self.assertEqual(child_result, b"child-error:SessionIntegrityError")
            self.assertEqual(self.generation_count(root, started.session), 2)
            run_id, digest = started.session.split(".", 1)
            self.assertEqual(
                len(original_successors(run_id, digest)),
                1,
            )

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_at_fork_child_resets_a_held_successor_registry_guard(self):
        session_module = sys.modules["audit_session"]
        read_result, write_result = os.pipe()
        session_module._SUCCESSOR_LOCKS_GUARD.acquire()
        child = os.fork()
        if child == 0:
            os.close(read_result)

            def timed_out(signum, frame):
                os._exit(91)

            signal.signal(signal.SIGALRM, timed_out)
            signal.alarm(1)
            try:
                with session_module._successor_transition_lock(
                    ("fork-reset-probe",)
                ):
                    os.write(write_result, b"child-ok")
                signal.alarm(0)
                os.close(write_result)
                os._exit(0)
            except Exception:
                os._exit(92)

        os.close(write_result)
        _, status = os.waitpid(child, 0)
        session_module._SUCCESSOR_LOCKS_GUARD.release()
        child_result = os.read(read_result, 1024)
        os.close(read_result)

        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)
        self.assertEqual(child_result, b"child-ok")

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_fresh_child_ofd_cannot_enter_parent_successor_transaction(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            run_id, digest = started.session.split(".", 1)
            transaction = (
                root / run_id / "claims" / digest / "transaction"
            )
            read_result, write_result = os.pipe()
            with store._successor_transaction_lock(lease):
                child = os.fork()
                if child == 0:
                    os.close(read_result)

                    def timed_out(signum, frame):
                        os._exit(91)

                    signal.signal(signal.SIGALRM, timed_out)
                    signal.alarm(1)
                    descriptor = os.open(
                        transaction,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    )
                    try:
                        try:
                            fcntl.flock(
                                descriptor,
                                fcntl.LOCK_EX | fcntl.LOCK_NB,
                            )
                            outcome = b"child-entered"
                        except BlockingIOError:
                            outcome = b"child-busy"
                        os.write(write_result, outcome)
                        signal.alarm(0)
                    finally:
                        os.close(descriptor)
                        os.close(write_result)
                    os._exit(0)

                os.close(write_result)
                _, status = os.waitpid(child, 0)
                child_result = os.read(read_result, 1024)
                os.close(read_result)
            lease.close()

            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
            self.assertEqual(child_result, b"child-busy")
            self.assertEqual(self.generation_count(root, started.session), 1)

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_fork_cannot_snapshot_lease_between_state_and_physical_close(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            descriptor = lease._descriptor
            original_state = store.load(started.session)
            session_module = sys.modules["audit_session"]
            original_close = session_module.os.close
            original_owned_close = (
                session_module._close_owned_descriptor
            )
            close_paused = threading.Event()
            release_close = threading.Event()
            delayed = False

            def paused_close(value):
                nonlocal delayed
                if value == descriptor and not delayed:
                    delayed = True
                    close_paused.set()
                    if not release_close.wait(2):
                        raise AssertionError("lease close was not released")
                return original_owned_close(value)

            closer = threading.Thread(target=lease.close)
            child_result_read, child_result_write = os.pipe()
            child_hold_read, child_hold_write = os.pipe()
            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                paused_close,
            ):
                closer.start()
                self.assertTrue(close_paused.wait(1))
                threading.Timer(0.1, release_close.set).start()
                child = os.fork()
                if child == 0:
                    original_close(child_result_read)
                    original_close(child_hold_write)
                    try:
                        os.fstat(descriptor)
                        outcome = b"child-fd-open"
                    except OSError:
                        outcome = b"child-fd-closed"
                    os.write(child_result_write, outcome)
                    os.read(child_hold_read, 1)
                    os._exit(0)

                original_close(child_result_write)
                original_close(child_hold_read)
                child_result = os.read(child_result_read, 1024)
                closer.join(timeout=1)
                terminal_state = {
                    **original_state,
                    "phase": "terminal",
                    "nonce": "a" * 32,
                    "response_name": f"{'b' * 32}.json",
                }
                try:
                    recovery = store.recover_claim(
                        started.session,
                        terminal_state,
                    )
                except Exception as error:
                    recovery = type(error).__name__
                os.write(child_hold_write, b"x")
                _, status = os.waitpid(child, 0)
                original_close(child_result_read)
                original_close(child_hold_write)

            self.assertFalse(closer.is_alive())
            self.assertEqual(child_result, b"child-fd-closed")
            self.assertEqual(recovery, "abandoned-claim-closed")
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_paused_lease_close_does_not_block_duplicate_audit(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            descriptor = lease._descriptor
            original_state = store.load(started.session)
            session_module = sys.modules["audit_session"]
            original_close = session_module._close_owned_descriptor
            close_paused = threading.Event()
            release_close = threading.Event()
            delayed = False
            before_fds = len(os.listdir("/proc/self/fd"))

            def paused_close(value):
                nonlocal delayed
                if value == descriptor and not delayed:
                    delayed = True
                    close_paused.set()
                    if not release_close.wait(2):
                        raise AssertionError("lease close was not released")
                return original_close(value)

            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                paused_close,
            ):
                closer = threading.Thread(target=lease.close)
                closer.start()
                self.assertTrue(close_paused.wait(1))
                before = time.monotonic()
                duplicate = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        started.session,
                        started.response_path,
                    )
                )
                elapsed = time.monotonic() - before
                release_close.set()
                closer.join(timeout=1)

            terminal_state = {
                **original_state,
                "phase": "terminal",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }
            recovery = store.recover_claim(
                started.session,
                terminal_state,
            )

            self.assertLess(elapsed, 0.75)
            self.assertEqual(duplicate.code, "SESSION_BUSY")
            self.assertFalse(closer.is_alive())
            self.assertEqual(recovery, "abandoned-claim-closed")
            self.assertEqual(
                len(os.listdir("/proc/self/fd")),
                before_fds - 1,
            )

    def test_paused_claim_open_does_not_block_an_independent_claim(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.start(repo, root / "first")
            second = self.start(repo, root / "second")
            first_store = self.module.SessionStore(root / "first")
            second_store = self.module.SessionStore(root / "second")
            session_module = sys.modules["audit_session"]
            original_open = session_module.os.open
            open_paused = threading.Event()
            release_open = threading.Event()
            delayed = False
            first_result = []

            def paused_open(path, flags, *args, **kwargs):
                nonlocal delayed
                descriptor = original_open(path, flags, *args, **kwargs)
                if (
                    isinstance(path, str)
                    and path.startswith(".")
                    and not delayed
                ):
                    delayed = True
                    open_paused.set()
                    if not release_open.wait(2):
                        raise AssertionError("claim open was not released")
                return descriptor

            def open_first():
                first_result.append(
                    first_store.claim_lease(first.session)
                )

            with mock.patch.object(
                session_module.os,
                "open",
                paused_open,
            ):
                worker = threading.Thread(target=open_first)
                worker.start()
                self.assertTrue(open_paused.wait(1))
                before = time.monotonic()
                second_lease = second_store.claim_lease(second.session)
                elapsed = time.monotonic() - before
                release_open.set()
                worker.join(timeout=1)

            self.assertLess(elapsed, 0.75)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(first_result), 1)
            first_result[0].close()
            second_lease.close()
            self.assertEqual(
                session_module._TRACKED_LEASE_OWNERSHIPS,
                set(),
            )

    def test_paused_transaction_open_does_not_block_independent_open(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.start(repo, root / "first")
            second = self.start(repo, root / "second")
            first_store = self.module.SessionStore(root / "first")
            second_store = self.module.SessionStore(root / "second")
            first_lease = first_store.claim_lease(first.session)
            second_lease = second_store.claim_lease(second.session)
            session_module = sys.modules["audit_session"]
            original_open = session_module.os.open
            open_paused = threading.Event()
            release_open = threading.Event()
            delayed = False

            def paused_open(path, flags, *args, **kwargs):
                nonlocal delayed
                descriptor = original_open(path, flags, *args, **kwargs)
                if path == "transaction" and not delayed:
                    delayed = True
                    open_paused.set()
                    if not release_open.wait(2):
                        raise AssertionError(
                            "transaction open was not released"
                        )
                return descriptor

            def open_first():
                with first_store._successor_transaction_lock(first_lease):
                    pass

            with mock.patch.object(
                session_module.os,
                "open",
                paused_open,
            ):
                worker = threading.Thread(target=open_first)
                worker.start()
                self.assertTrue(open_paused.wait(1))
                before = time.monotonic()
                with second_store._successor_transaction_lock(second_lease):
                    pass
                elapsed = time.monotonic() - before
                release_open.set()
                worker.join(timeout=1)

            first_lease.close()
            second_lease.close()
            self.assertLess(elapsed, 0.75)
            self.assertFalse(worker.is_alive())
            deadline = time.monotonic() + 1
            while session_module._TRACKED_TRANSACTION_OWNERSHIPS:
                if time.monotonic() >= deadline:
                    self.fail("transaction cleanup did not finish")
                time.sleep(0.005)
            self.assertEqual(
                session_module._TRACKED_TRANSACTION_OWNERSHIPS,
                set(),
            )

    def test_paused_transaction_close_returns_busy_without_fd_growth(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            original_state = store.load(started.session)
            session_module = sys.modules["audit_session"]
            original_close = session_module._close_owned_descriptor
            transaction_entered = threading.Event()
            exit_transaction = threading.Event()
            close_paused = threading.Event()
            release_close = threading.Event()
            captured = []
            before_fds = len(os.listdir("/proc/self/fd"))

            def paused_close(descriptor):
                if captured and descriptor == captured[0]:
                    close_paused.set()
                    if not release_close.wait(2):
                        raise AssertionError(
                            "transaction close was not released"
                        )
                return original_close(descriptor)

            def hold_transaction():
                with store._successor_transaction_lock(lease):
                    captured.extend(
                        descriptor
                        for descriptor, _ in
                        session_module._TRACKED_TRANSACTION_OWNERSHIPS
                    )
                    transaction_entered.set()
                    exit_transaction.wait(2)

            next_state = {
                **original_state,
                "phase": "reconciliation",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }
            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                paused_close,
            ):
                worker = threading.Thread(target=hold_transaction)
                worker.start()
                self.assertTrue(transaction_entered.wait(1))
                exit_transaction.set()
                self.assertTrue(close_paused.wait(1))
                before = time.monotonic()
                with self.assertRaises(self.module.SessionBusyError):
                    store.append_claimed(
                        started.session,
                        next_state,
                        {"schema_version": 1, "kind": "reconciliation"},
                        lease=lease,
                    )
                elapsed = time.monotonic() - before
                release_close.set()
                worker.join(timeout=1)

            result = store.append_claimed(
                started.session,
                next_state,
                {"schema_version": 1, "kind": "reconciliation"},
                lease=lease,
            )
            lease.close()

            self.assertLess(elapsed, 0.75)
            self.assertFalse(worker.is_alive())
            self.assertEqual(packet_of(result)["kind"], "reconciliation")
            self.assertEqual(len(os.listdir("/proc/self/fd")), before_fds - 1)

    def test_lease_pending_handoff_cannot_miss_parent_cleanup(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            descriptor = lease._descriptor
            session_module = sys.modules["audit_session"]
            session_module._before_fork()
            closer = threading.Thread(target=lease.close)
            closer.start()
            closer.join(timeout=1)
            self.assertFalse(closer.is_alive())
            os.fstat(descriptor)
            session_module._after_fork_parent()
            deadline = time.monotonic() + 1
            while (
                (descriptor, lease._tracking_token)
                in session_module._TRACKED_LEASE_OWNERSHIPS
            ):
                if time.monotonic() >= deadline:
                    self.fail("queued lease cleanup was not resumed")
                time.sleep(0.005)

            with self.assertRaises(OSError):
                os.fstat(descriptor)
            self.assertEqual(
                session_module._PENDING_LEASE_CLOSE_FDS,
                set(),
            )
            self.assertEqual(
                session_module._TRACKED_LEASE_OWNERSHIPS,
                set(),
            )

    def test_transaction_pending_handoff_cannot_miss_parent_cleanup(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            session_module = sys.modules["audit_session"]
            transaction_entered = threading.Event()
            exit_transaction = threading.Event()
            captured = []

            def hold_transaction():
                with store._successor_transaction_lock(lease):
                    captured.extend(
                        descriptor
                        for descriptor, _ in
                        session_module._TRACKED_TRANSACTION_OWNERSHIPS
                    )
                    transaction_entered.set()
                    exit_transaction.wait(2)

            worker = threading.Thread(target=hold_transaction)
            worker.start()
            self.assertTrue(transaction_entered.wait(1))
            session_module._before_fork()
            exit_transaction.set()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            os.fstat(captured[0])
            session_module._after_fork_parent()
            deadline = time.monotonic() + 1
            while session_module._TRACKED_TRANSACTION_OWNERSHIPS:
                if time.monotonic() >= deadline:
                    self.fail("queued transaction cleanup was not resumed")
                time.sleep(0.005)
            lease.close()

            with self.assertRaises(OSError):
                os.fstat(captured[0])
            self.assertEqual(
                session_module._PENDING_TRANSACTION_CLOSE_FDS,
                set(),
            )
            self.assertEqual(
                session_module._TRACKED_TRANSACTION_OWNERSHIPS,
                set(),
            )

    def test_concurrent_pending_drainers_close_one_fd_exactly_once(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        token = object()
        session_module._TRACKED_LEASE_OWNERSHIPS.add(
            (descriptor, token)
        )
        session_module._PENDING_LEASE_CLOSE_FDS.add(
            (descriptor, token)
        )
        errors = []

        def drain():
            try:
                session_module._close_pending_ownership(
                    "lease",
                    (descriptor, token),
                )
            except Exception as error:
                errors.append(error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: drain(), range(2)))

        self.assertEqual(errors, [])
        self.assertEqual(
            session_module._PENDING_LEASE_CLOSE_FDS,
            set(),
        )
        self.assertNotIn(
            (descriptor, token),
            session_module._TRACKED_LEASE_OWNERSHIPS,
        )
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_audit_lifecycle_never_drains_unrelated_pending_close(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            descriptor = lease._descriptor
            token = lease._tracking_token
            session_module = sys.modules["audit_session"]
            close_called = threading.Event()
            original_close = session_module._close_owned_descriptor

            def observed_close(value):
                if value == descriptor:
                    close_called.set()
                return original_close(value)

            session_module._PENDING_LEASE_CLOSE_FDS.add(
                (descriptor, token)
            )
            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                observed_close,
            ):
                before = time.monotonic()
                with session_module._audit_fd_lifecycle():
                    pass
                elapsed = time.monotonic() - before
                self.assertFalse(close_called.is_set())
                session_module._PENDING_LEASE_CLOSE_FDS.discard(
                    (descriptor, token)
                )
                lease.close()

            self.assertLess(elapsed, 0.75)
            self.assertTrue(close_called.is_set())

    def test_audit_exit_is_prompt_while_gate_metadata_is_held(self):
        session_module = sys.modules["audit_session"]
        gate = session_module._FORK_FD_LIFECYCLE_GATE
        body_entered = threading.Event()
        leave_body = threading.Event()
        finished = threading.Event()

        def use_lifecycle():
            with session_module._audit_fd_lifecycle():
                body_entered.set()
                leave_body.wait(1)
            finished.set()

        worker = threading.Thread(target=use_lifecycle)
        worker.start()
        self.assertTrue(body_entered.wait(1))
        gate._metadata.acquire()
        try:
            leave_body.set()
            self.assertTrue(finished.wait(0.25))
        finally:
            gate._metadata.release()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        session_module._before_fork()
        session_module._after_fork_parent()

    def test_authenticated_continue_exits_reader_before_deadline_when_metadata_is_held(
        self,
    ):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.runtime(root)
            started = runtime.advance(
                self.module.StartAudit(
                    self.target(repo),
                    deadline_seconds=1,
                )
            )
            write_response(started.response_path, code_response(started))
            session_module = sys.modules["audit_session"]
            original_open = self.module.SessionStore._open_directory
            claim_opened = threading.Event()
            release_open = threading.Event()
            result = []

            def paused_claim_open(store, name, *, dir_fd=None):
                descriptor = original_open(
                    store,
                    name,
                    dir_fd=dir_fd,
                )
                if (
                    isinstance(name, str)
                    and name.startswith(".")
                    and not claim_opened.is_set()
                ):
                    claim_opened.set()
                    release_open.wait(1)
                return descriptor

            def continue_audit():
                result.append(
                    runtime.advance(
                        self.module.ContinueAudit(
                            started.session,
                            started.response_path,
                        )
                    )
                )

            with mock.patch.object(
                self.module.SessionStore,
                "_open_directory",
                paused_claim_open,
            ):
                worker = threading.Thread(target=continue_audit)
                worker.start()
                self.assertTrue(claim_opened.wait(1))
                session_module._FORK_FD_LIFECYCLE_GATE._metadata.acquire()
                try:
                    release_open.set()
                    self.assertTrue(
                        worker.join(timeout=0.75) is None
                        and not worker.is_alive()
                    )
                finally:
                    session_module._FORK_FD_LIFECYCLE_GATE._metadata.release()
                worker.join(timeout=1)

            self.assertFalse(worker.is_alive())
            self.assertEqual(len(result), 1)
            session_module._before_fork()
            session_module._after_fork_parent()

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_parent_fork_return_does_not_wait_for_deferred_physical_close(
        self,
    ):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        original_close = session_module._close_owned_descriptor
        parent_pid = os.getpid()
        close_paused = threading.Event()
        release_close = threading.Event()

        def paused_parent_close(value):
            if os.getpid() == parent_pid and value == descriptor:
                close_paused.set()
                release_close.wait(2)
            return original_close(value)

        with mock.patch.object(
            session_module,
            "_close_owned_descriptor",
            paused_parent_close,
        ):
            with session_module._ownership_publication():
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                before = time.monotonic()
                child = os.fork()
                elapsed = time.monotonic() - before
                if child == 0:
                    os._exit(0)
            _, status = os.waitpid(child, 0)
            self.assertLess(elapsed, 0.75)
            self.assertTrue(close_paused.wait(1))
            release_close.set()

        deadline = time.monotonic() + 1
        while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
            if time.monotonic() >= deadline:
                self.fail("deferred parent close did not finish")
            time.sleep(0.005)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_fork_child_replaces_cleanup_queue_and_worker(self):
        session_module = sys.modules["audit_session"]
        result_read, result_write = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(result_read)
            descriptor = os.open(
                "/dev/null",
                os.O_RDONLY | os.O_CLOEXEC,
            )
            token = object()
            ownership = (descriptor, token)
            session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
            session_module._PENDING_LEASE_CLOSE_FDS.add(ownership)
            session_module._schedule_pending_cleanup(
                "lease",
                ownership,
            )
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try:
                    os.fstat(descriptor)
                except OSError:
                    os.write(result_write, b"closed")
                    os._exit(0)
                time.sleep(0.005)
            os.write(result_write, b"open")
            os._exit(1)

        os.close(result_write)
        outcome = os.read(result_read, 1024)
        _, status = os.waitpid(child, 0)
        os.close(result_read)

        self.assertEqual(outcome, b"closed")
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_parent_cleanup_transfer_retries_eio_outside_callback(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        original_close = session_module._close_owned_descriptor
        attempts = 0

        def transient_close(value):
            nonlocal attempts
            if value == descriptor:
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.EIO, "transient close failure")
            return original_close(value)

        session_module._before_fork()
        session_module._schedule_pending_cleanup("lease", ownership)
        with mock.patch.object(
            session_module,
            "_close_owned_descriptor",
            transient_close,
        ):
            before = time.monotonic()
            session_module._after_fork_parent()
            elapsed = time.monotonic() - before
            deadline = time.monotonic() + 1
            while attempts < 2 and time.monotonic() < deadline:
                time.sleep(0.005)

        self.assertLess(elapsed, 0.25)
        self.assertGreaterEqual(attempts, 2)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_cleanup_handoff_survives_thread_start_failure(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            lease = self.module.SessionStore(root).claim_lease(
                started.session
            )
            descriptor = lease._descriptor
            session_module = sys.modules["audit_session"]
            gate = session_module._FORK_FD_LIFECYCLE_GATE

            gate._metadata.acquire()
            try:
                with mock.patch.object(
                    session_module.threading.Thread,
                    "start",
                    side_effect=RuntimeError("thread unavailable"),
                ):
                    lease.close()
            finally:
                gate._metadata.release()

            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try:
                    os.fstat(descriptor)
                except OSError:
                    break
                time.sleep(0.005)
            with self.assertRaises(OSError):
                os.fstat(descriptor)
            self.assertEqual(
                session_module._PENDING_LEASE_CLOSE_FDS,
                set(),
            )

    def test_direct_lease_close_retries_eio_without_losing_ownership(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            lease = self.module.SessionStore(root).claim_lease(
                started.session
            )
            descriptor = lease._descriptor
            session_module = sys.modules["audit_session"]
            original_close = session_module._close_owned_descriptor
            attempts = 0

            def transient_close(value):
                nonlocal attempts
                if value == descriptor:
                    attempts += 1
                    if attempts == 1:
                        raise OSError(errno.EIO, "transient close failure")
                return original_close(value)

            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                transient_close,
            ):
                lease.close()
                deadline = time.monotonic() + 1
                while attempts < 2 and time.monotonic() < deadline:
                    time.sleep(0.005)

            self.assertGreaterEqual(attempts, 2)
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_direct_tracked_claim_close_retries_eio(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        session_module._TRACKED_LEASE_OWNERSHIPS.add(
            (descriptor, token)
        )
        store = self.module.SessionStore(Path("/unused"))
        store._tracked_claim_ownerships[descriptor] = (
            descriptor,
            token,
        )
        original_close = session_module._close_owned_descriptor
        attempts = 0

        def transient_close(value):
            nonlocal attempts
            if value == descriptor:
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.EIO, "transient close failure")
            return original_close(value)

        with mock.patch.object(
            session_module,
            "_close_owned_descriptor",
            transient_close,
        ):
            store._close_tracked_claim_descriptor(descriptor)
            deadline = time.monotonic() + 1
            while attempts < 2 and time.monotonic() < deadline:
                time.sleep(0.005)

        self.assertGreaterEqual(attempts, 2)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_direct_transaction_close_retries_eio(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            session_module = sys.modules["audit_session"]
            original_close = session_module._close_owned_descriptor
            captured = []
            attempts = 0

            def transient_close(value):
                nonlocal attempts
                if captured and value == captured[0]:
                    attempts += 1
                    if attempts == 1:
                        raise OSError(errno.EIO, "transient close failure")
                return original_close(value)

            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                transient_close,
            ):
                with store._successor_transaction_lock(lease):
                    captured.extend(
                        descriptor
                        for descriptor, _ in
                        session_module._TRACKED_TRANSACTION_OWNERSHIPS
                    )
                deadline = time.monotonic() + 1
                while attempts < 2 and time.monotonic() < deadline:
                    time.sleep(0.005)

            lease.close()
            self.assertGreaterEqual(attempts, 2)
            with self.assertRaises(OSError):
                os.fstat(captured[0])

    def test_background_close_retries_eio_without_future_audit(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        session_module._TRACKED_LEASE_OWNERSHIPS.add(
            (descriptor, token)
        )
        session_module._PENDING_LEASE_CLOSE_FDS.add((descriptor, token))
        original_close = session_module._close_owned_descriptor
        attempts = 0

        def transient_close(value):
            nonlocal attempts
            if value == descriptor:
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.EIO, "transient close failure")
            return original_close(value)

        with mock.patch.object(
            session_module,
            "_close_owned_descriptor",
            transient_close,
        ):
            session_module._schedule_pending_cleanup(
                "lease",
                (descriptor, token),
            )
            deadline = time.monotonic() + 1
            while attempts < 2 and time.monotonic() < deadline:
                time.sleep(0.005)

        self.assertGreaterEqual(attempts, 2)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_stale_cleanup_cannot_unregister_a_reused_tracked_fd(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        stale_token = object()
        replacement_token = object()
        session_module._TRACKED_LEASE_OWNERSHIPS.add(
            (descriptor, stale_token)
        )
        session_module._PENDING_LEASE_CLOSE_FDS.add(
            (descriptor, stale_token)
        )
        original_close_owned = session_module._close_owned_descriptor
        replacement = []

        def close_then_reuse(value):
            original_close_owned(value)
            reused = os.open(
                "/dev/null",
                os.O_RDONLY | os.O_CLOEXEC,
            )
            self.assertEqual(reused, value)
            replacement.append(reused)
            session_module._TRACKED_LEASE_OWNERSHIPS.add(
                (reused, replacement_token)
            )

        with mock.patch.object(
            session_module,
            "_close_owned_descriptor",
            close_then_reuse,
        ):
            self.assertTrue(
                session_module._close_pending_ownership(
                    "lease",
                    (descriptor, stale_token),
                )
            )

        self.assertEqual(replacement, [descriptor])
        self.assertIn(
            (descriptor, replacement_token),
            session_module._TRACKED_LEASE_OWNERSHIPS,
        )
        os.fstat(descriptor)
        os.close(descriptor)
        session_module._TRACKED_LEASE_OWNERSHIPS.discard(
            (descriptor, replacement_token)
        )

    def test_cleanup_exclusion_precedes_reused_fd_publication(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        stale_token = object()
        stale_ownership = (descriptor, stale_token)
        session_module._TRACKED_LEASE_OWNERSHIPS.add(stale_ownership)
        session_module._PENDING_LEASE_CLOSE_FDS.add(stale_ownership)
        original_close = session_module._close_owned_descriptor
        physically_closed = threading.Event()
        release_cleanup = threading.Event()

        def close_then_pause(value):
            original_close(value)
            if value == descriptor:
                physically_closed.set()
                release_cleanup.wait(2)

        cleanup = threading.Thread(
            target=session_module._close_pending_ownership,
            args=("lease", stale_ownership),
        )
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            session_module,
            "_close_owned_descriptor",
            close_then_pause,
        ):
            parent = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            os.mkdir("replacement", dir_fd=parent)
            cleanup.start()
            self.assertTrue(physically_closed.wait(1))
            before = time.monotonic()
            with self.assertRaises(self.module.SessionBusyError):
                self.module.SessionStore(
                    Path(temporary)
                )._open_tracked_claim_directory(
                    "replacement",
                    dir_fd=parent,
                )
            elapsed = time.monotonic() - before
            release_cleanup.set()
            cleanup.join(timeout=1)
            replacement = self.module.SessionStore(
                Path(temporary)
            )._open_tracked_claim_directory(
                "replacement",
                dir_fd=parent,
            )
            lease = session_module.ClaimLease(
                self.module.SessionStore(Path(temporary)),
                "a" * 32,
                "b" * 64,
                replacement,
            )
            lease.close()
            os.close(parent)

        self.assertLess(elapsed, 0.75)
        self.assertFalse(cleanup.is_alive())

    def test_cleanup_writer_intent_stops_overlapping_publisher_relay(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        gate = session_module._DESCRIPTOR_OWNERSHIP_GATE
        current = gate.try_enter_publication()
        self.assertIsNotNone(current)
        session_module._schedule_pending_cleanup("lease", ownership)
        rejected = False
        admitted = 0
        started_relay = time.monotonic()
        deadline = time.monotonic() + 0.6
        try:
            while time.monotonic() < deadline:
                next_publisher = gate.try_enter_publication()
                if next_publisher is None:
                    rejected = True
                    break
                gate.exit_publication(current)
                current = next_publisher
                admitted += 1
        finally:
            gate.exit_publication(current)

        self.assertTrue(rejected)
        self.assertLess(time.monotonic() - started_relay, 0.25)
        deadline = time.monotonic() + 1
        while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
            if time.monotonic() >= deadline:
                self.fail("writer intent did not complete cleanup")
            time.sleep(0.005)
        with self.assertRaises(OSError):
            os.fstat(descriptor)
        publisher = gate.try_enter_publication()
        self.assertIsNotNone(publisher)
        gate.exit_publication(publisher)

    def test_cleanup_release_handoff_keeps_publication_excluded(self):
        session_module = sys.modules["audit_session"]
        gate = session_module._DescriptorOwnershipGate()
        first_key = ("lease", (10_000_010, object()))
        second_key = ("lease", (10_000_011, object()))
        cleanup, intent_key, intent_token = gate.try_enter_cleanup(
            first_key
        )

        self.assertEqual(intent_key, first_key)
        self.assertIs(gate._writer_intents[first_key], intent_token)
        del gate._writer_intents[first_key]
        self.assertIsNone(gate.try_enter_publication())
        self.assertIsNone(gate.try_enter_cleanup(second_key))
        cleanup.release()

        self.assertIn(second_key, gate._writer_intents)
        self.assertIsNone(gate.try_enter_publication())
        gate._writer_intents.clear()

    def test_unrelated_cleanup_cannot_release_ambiguous_close_intent(self):
        session_module = sys.modules["audit_session"]
        ambiguous = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        unrelated = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        ambiguous_ownership = (ambiguous, object())
        unrelated_ownership = (unrelated, object())
        original_close = session_module._close_owned_descriptor
        ambiguous_attempted = threading.Event()
        allow_ambiguous_close = threading.Event()

        def fail_before_close(value):
            if value == ambiguous:
                ambiguous_attempted.set()
                if not allow_ambiguous_close.is_set():
                    raise OSError(errno.EIO, "close not attempted")
            return original_close(value)

        session_module._TRACKED_LEASE_OWNERSHIPS.update(
            {ambiguous_ownership, unrelated_ownership}
        )
        try:
            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                fail_before_close,
            ):
                session_module._schedule_pending_cleanup(
                    "lease",
                    ambiguous_ownership,
                )
                self.assertTrue(ambiguous_attempted.wait(1))
                session_module._schedule_pending_cleanup(
                    "lease",
                    unrelated_ownership,
                )
                deadline = time.monotonic() + 1
                while (
                    unrelated_ownership
                    in session_module._TRACKED_LEASE_OWNERSHIPS
                ):
                    if time.monotonic() >= deadline:
                        self.fail("unrelated cleanup did not finish")
                    time.sleep(0.005)

                self.assertIn(
                    ambiguous_ownership,
                    session_module._PENDING_LEASE_CLOSE_FDS,
                )
                self.assertIsNone(
                    session_module._DESCRIPTOR_OWNERSHIP_GATE
                    .try_enter_publication()
                )
                allow_ambiguous_close.set()
                deadline = time.monotonic() + 1
                while (
                    ambiguous_ownership
                    in session_module._TRACKED_LEASE_OWNERSHIPS
                ):
                    if time.monotonic() >= deadline:
                        self.fail("ambiguous cleanup did not recover")
                    time.sleep(0.005)

            publisher = (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                .try_enter_publication()
            )
            self.assertIsNotNone(publisher)
            (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                .exit_publication(publisher)
            )
        finally:
            allow_ambiguous_close.set()
            for ownership in (
                ambiguous_ownership,
                unrelated_ownership,
            ):
                session_module._TRACKED_LEASE_OWNERSHIPS.discard(
                    ownership
                )
                session_module._PENDING_LEASE_CLOSE_FDS.discard(
                    ownership
                )
            (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                ._writer_intents.clear()
            )
            for descriptor in (ambiguous, unrelated):
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def test_single_slot_close_preserves_same_inode_untracked_reuse(self):
        session_module = sys.modules["audit_session"]
        with tempfile.TemporaryDirectory() as temporary:
            store = self.module.SessionStore(Path(temporary))
            descriptor = store._open_directory(temporary)
            ownership = (descriptor, object())
            original_close = session_module.os.close
            replacement = []

            def close_reopen_same_directory(first, last, flags):
                self.assertEqual(
                    (first, last, flags),
                    (descriptor, descriptor, 0),
                )
                original_close(descriptor)
                replacement.append(
                    store._open_directory(temporary)
                )
                return 0

            session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
            try:
                with mock.patch.object(
                    session_module,
                    "_CLOSE_RANGE",
                    close_reopen_same_directory,
                ):
                    self.assertTrue(
                        session_module._close_pending_ownership(
                            "lease",
                            ownership,
                        )
                    )

                self.assertEqual(replacement, [descriptor])
                original_metadata = os.stat(temporary)
                replacement_metadata = os.fstat(replacement[0])
                self.assertEqual(
                    (
                        replacement_metadata.st_dev,
                        replacement_metadata.st_ino,
                    ),
                    (
                        original_metadata.st_dev,
                        original_metadata.st_ino,
                    ),
                )
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                time.sleep(0.05)
                os.fstat(replacement[0])
                publisher = (
                    session_module._DESCRIPTOR_OWNERSHIP_GATE
                    .try_enter_publication()
                )
                self.assertIsNotNone(publisher)
                (
                    session_module._DESCRIPTOR_OWNERSHIP_GATE
                    .exit_publication(publisher)
                )
            finally:
                session_module._TRACKED_LEASE_OWNERSHIPS.discard(
                    ownership
                )
                session_module._PENDING_LEASE_CLOSE_FDS.discard(
                    ownership
                )
                (
                    session_module._DESCRIPTOR_OWNERSHIP_GATE
                    ._writer_intents.clear()
                )
                for value in replacement or [descriptor]:
                    try:
                        os.close(value)
                    except OSError:
                        pass

    def test_single_slot_close_preserves_same_ofd_fd_reuse(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        duplicate = os.dup(descriptor)
        ownership = (descriptor, object())
        replacement = []

        def close_then_reuse_same_ofd(first, last, flags):
            self.assertEqual((first, last, flags), (descriptor,) * 2 + (0,))
            os.close(descriptor)
            replacement.append(os.dup(duplicate))
            self.assertEqual(replacement, [descriptor])
            return 0

        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        try:
            with mock.patch.object(
                session_module,
                "_CLOSE_RANGE",
                close_then_reuse_same_ofd,
            ):
                self.assertTrue(
                    session_module._close_pending_ownership(
                        "lease",
                        ownership,
                    )
                )

            session_module._schedule_pending_cleanup(
                "lease",
                ownership,
            )
            time.sleep(0.05)
            os.fstat(replacement[0])
        finally:
            session_module._TRACKED_LEASE_OWNERSHIPS.discard(
                ownership
            )
            session_module._PENDING_LEASE_CLOSE_FDS.discard(
                ownership
            )
            (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                ._writer_intents.clear()
            )
            for value in replacement + [duplicate, descriptor]:
                try:
                    os.close(value)
                except OSError:
                    pass

    def test_single_slot_close_failure_never_touches_descriptor(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )

        def blocked_close_range(first, last, flags):
            ctypes.set_errno(errno.EPERM)
            return -1

        try:
            with mock.patch.object(
                session_module,
                "_CLOSE_RANGE",
                blocked_close_range,
            ):
                with self.assertRaises(OSError) as raised:
                    session_module._close_owned_descriptor(descriptor)
            self.assertEqual(raised.exception.errno, errno.EPERM)
            os.fstat(descriptor)
        finally:
            os.close(descriptor)

    def test_unavailable_single_slot_close_never_uses_raw_close(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        try:
            with mock.patch.object(
                session_module,
                "_CLOSE_RANGE",
                None,
            ), mock.patch.object(
                session_module.os,
                "close",
                side_effect=AssertionError("raw close fallback"),
            ):
                with self.assertRaises(OSError) as raised:
                    session_module._close_owned_descriptor(descriptor)
            self.assertEqual(raised.exception.errno, errno.ENOSYS)
            os.fstat(descriptor)
        finally:
            os.close(descriptor)

    def test_single_slot_close_has_no_guard_or_ofd_probe(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        try:
            self.assertFalse(
                hasattr(
                    session_module,
                    "_same_open_file_description",
                )
            )
            with mock.patch.object(
                session_module.os,
                "dup",
                side_effect=AssertionError("unexpected close guard"),
            ), mock.patch.object(
                session_module.fcntl,
                "fcntl",
                side_effect=OSError(errno.EINVAL, "unexpected OFD probe"),
            ):
                session_module._close_owned_descriptor(descriptor)
            with self.assertRaises(OSError):
                os.fstat(descriptor)
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

    def test_child_snapshot_does_not_retry_same_ofd_reuse(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open(
            "/dev/null",
            os.O_RDONLY | os.O_CLOEXEC,
        )
        duplicate = os.dup(descriptor)
        ownership = (descriptor, object())
        replacement = []
        calls = 0

        def close_then_reuse(first, last, flags):
            nonlocal calls
            calls += 1
            os.close(descriptor)
            replacement.append(os.dup(duplicate))
            self.assertEqual(replacement, [descriptor])
            return 0

        try:
            with mock.patch.object(
                session_module,
                "_CLOSE_RANGE",
                close_then_reuse,
            ):
                failed = session_module._close_child_snapshot(
                    {ownership}
                )
            self.assertEqual(failed, set())
            self.assertEqual(calls, 1)
            os.fstat(replacement[0])
        finally:
            for value in replacement + [duplicate, descriptor]:
                try:
                    os.close(value)
                except OSError:
                    pass

    def test_stale_job_cannot_release_another_jobs_intent(self):
        session_module = sys.modules["audit_session"]
        gate = session_module._DescriptorOwnershipGate()
        unresolved = ("lease", (10_000_020, object()))
        stale = ("lease", (10_000_021, object()))

        cleanup, key, token = gate.try_enter_cleanup(unresolved)
        gate.exit_cleanup(
            cleanup,
            key,
            token,
            retain_intent=True,
        )
        cleanup, key, token = gate.try_enter_cleanup(stale)
        gate.exit_cleanup(
            cleanup,
            key,
            token,
            retain_intent=False,
        )

        self.assertIn(unresolved, gate._writer_intents)
        self.assertNotIn(stale, gate._writer_intents)
        self.assertIsNone(gate.try_enter_publication())
        cleanup, key, token = gate.try_enter_cleanup(unresolved)
        gate.exit_cleanup(
            cleanup,
            key,
            token,
            retain_intent=False,
        )
        publisher = gate.try_enter_publication()
        self.assertIsNotNone(publisher)
        gate.exit_publication(publisher)

    def test_stale_exact_cleanup_job_cannot_close_reused_descriptor(self):
        session_module = sys.modules["audit_session"]
        with tempfile.TemporaryDirectory() as temporary:
            parent = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            os.mkdir("replacement", dir_fd=parent)
            descriptor = os.open(
                "/dev/null",
                os.O_RDONLY | os.O_CLOEXEC,
            )
            stale_token = object()
            stale_ownership = (descriptor, stale_token)
            session_module._TRACKED_LEASE_OWNERSHIPS.add(
                stale_ownership
            )
            session_module._schedule_pending_cleanup(
                "lease",
                stale_ownership,
            )
            deadline = time.monotonic() + 1
            while (
                stale_ownership
                in session_module._TRACKED_LEASE_OWNERSHIPS
            ):
                if time.monotonic() >= deadline:
                    self.fail("stale ownership did not close")
                time.sleep(0.005)

            store = self.module.SessionStore(Path(temporary))
            replacement = store._open_tracked_claim_directory(
                "replacement",
                dir_fd=parent,
            )
            self.assertEqual(replacement, descriptor)
            lease = session_module.ClaimLease(
                store,
                "a" * 32,
                "b" * 64,
                replacement,
            )
            replacement_ownership = (
                replacement,
                lease._tracking_token,
            )
            session_module._schedule_pending_cleanup(
                "lease",
                stale_ownership,
            )
            time.sleep(0.05)

            os.fstat(replacement)
            self.assertFalse(lease.closed)
            self.assertIn(
                replacement_ownership,
                session_module._TRACKED_LEASE_OWNERSHIPS,
            )
            lease.close()
            os.close(parent)

    def test_scheduler_does_not_scan_a_concurrently_mutated_pending_set(self):
        session_module = sys.modules["audit_session"]
        original_pending = session_module._PENDING_LEASE_CLOSE_FDS
        errors = []

        class NoScanSet(set):
            def __iter__(self):
                raise AssertionError("scheduler scanned pending ownership")

        first = (10_000_001, object())
        second = (10_000_002, object())
        session_module._PENDING_LEASE_CLOSE_FDS = NoScanSet({first})
        stop_mutating = threading.Event()

        def mutate():
            while not stop_mutating.is_set():
                session_module._PENDING_LEASE_CLOSE_FDS.add(second)
                session_module._PENDING_LEASE_CLOSE_FDS.discard(second)

        def schedule_many():
            try:
                for _ in range(100):
                    session_module._schedule_pending_cleanup(
                        "lease",
                        first,
                    )
            except Exception as error:
                errors.append(error)

        mutator = threading.Thread(target=mutate)
        worker = threading.Thread(target=schedule_many)
        mutator.start()
        worker.start()
        worker.join(timeout=1)
        stop_mutating.set()
        mutator.join(timeout=1)
        session_module._PENDING_LEASE_CLOSE_FDS = original_pending

        self.assertFalse(worker.is_alive())
        self.assertFalse(mutator.is_alive())
        self.assertEqual(errors, [])

    def test_dead_cleanup_executor_is_restarted_by_later_schedule(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        original_queue = session_module._CLEANUP_QUEUE
        original_thread = session_module._CLEANUP_THREAD
        replacement_queue = session_module.queue.SimpleQueue()

        class DeadThread:
            def is_alive(self):
                return False

        session_module._CLEANUP_QUEUE = replacement_queue
        session_module._CLEANUP_THREAD = DeadThread()
        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        session_module._PENDING_LEASE_CLOSE_FDS.add(ownership)
        try:
            session_module._schedule_pending_cleanup(
                "lease",
                ownership,
            )
            deadline = time.monotonic() + 1
            while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
                if time.monotonic() >= deadline:
                    self.fail("dead cleanup executor was not restarted")
                time.sleep(0.005)
        finally:
            session_module._CLEANUP_QUEUE = original_queue
            session_module._CLEANUP_THREAD = original_thread

        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_one_schedule_recovers_one_shot_worker_start_failure(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        original_queue = session_module._CLEANUP_QUEUE
        original_thread = session_module._CLEANUP_THREAD
        replacement_queue = session_module.queue.SimpleQueue()
        original_start = session_module.threading.Thread.start
        starts = 0

        class DeadThread:
            def is_alive(self):
                return False

        def fail_once(thread):
            nonlocal starts
            starts += 1
            if starts == 1:
                raise RuntimeError("transient thread start failure")
            return original_start(thread)

        session_module._CLEANUP_QUEUE = replacement_queue
        session_module._CLEANUP_THREAD = DeadThread()
        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        try:
            with mock.patch.object(
                session_module.threading.Thread,
                "start",
                fail_once,
            ):
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                deadline = time.monotonic() + 1
                while (
                    ownership
                    in session_module._TRACKED_LEASE_OWNERSHIPS
                ):
                    if time.monotonic() >= deadline:
                        self.fail(
                            "one-shot start failure was not recovered"
                        )
                    time.sleep(0.005)
        finally:
            session_module._CLEANUP_QUEUE = original_queue
            session_module._CLEANUP_THREAD = original_thread

        self.assertGreaterEqual(starts, 2)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_cleanup_worker_contains_unexpected_job_exception(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        original_close_record = session_module._close_owned_record
        attempts = 0

        def fail_once(kind, value):
            nonlocal attempts
            if value == ownership:
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("unexpected cleanup failure")
            return original_close_record(kind, value)

        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        with mock.patch.object(
            session_module,
            "_close_owned_record",
            fail_once,
        ):
            session_module._schedule_pending_cleanup(
                "lease",
                ownership,
            )
            deadline = time.monotonic() + 1
            while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
                if time.monotonic() >= deadline:
                    self.fail("cleanup worker did not contain and retry")
                time.sleep(0.005)

        self.assertGreaterEqual(attempts, 2)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_cleanup_worker_system_exit_handoffs_and_restarts(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        token = object()
        ownership = (descriptor, token)
        original_close_record = session_module._close_owned_record
        crashed_worker = None
        attempts = 0

        def crash_once(kind, value):
            nonlocal attempts, crashed_worker
            if value == ownership:
                attempts += 1
                if attempts == 1:
                    crashed_worker = threading.current_thread()
                    raise SystemExit("injected cleanup worker crash")
            return original_close_record(kind, value)

        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        try:
            with mock.patch.object(
                session_module,
                "_close_owned_record",
                crash_once,
            ):
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                deadline = time.monotonic() + 1
                while (
                    ownership
                    in session_module._TRACKED_LEASE_OWNERSHIPS
                ):
                    if time.monotonic() >= deadline:
                        self.fail(
                            "crashed cleanup worker lost its exact job"
                        )
                    time.sleep(0.005)

            self.assertGreaterEqual(attempts, 2)
            self.assertIsNotNone(crashed_worker)
            crashed_worker.join(timeout=1)
            self.assertFalse(crashed_worker.is_alive())
            self.assertIsNot(
                session_module._CLEANUP_THREAD,
                crashed_worker,
            )
            self.assertTrue(session_module._CLEANUP_THREAD.is_alive())
            self.assertNotIn(
                ownership,
                session_module._PENDING_LEASE_CLOSE_FDS,
            )
            publisher = (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                .try_enter_publication()
            )
            self.assertIsNotNone(publisher)
            (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                .exit_publication(publisher)
            )
            with self.assertRaises(OSError):
                os.fstat(descriptor)
        finally:
            (
                session_module._DESCRIPTOR_OWNERSHIP_GATE
                ._writer_intents.clear()
            )
            session_module._TRACKED_LEASE_OWNERSHIPS.discard(
                ownership
            )
            session_module._PENDING_LEASE_CLOSE_FDS.discard(
                ownership
            )
            try:
                os.close(descriptor)
            except OSError:
                pass

    def test_direct_lease_keyboard_interrupt_queues_exact_cleanup(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        store = self.module.SessionStore(Path("/unused"))
        lease = session_module.ClaimLease(
            store,
            "a" * 32,
            "b" * 64,
            descriptor,
        )
        ownership = (descriptor, lease._tracking_token)
        original_close_record = session_module._close_owned_record
        interrupted = False

        def interrupt_once(kind, value):
            nonlocal interrupted
            if value == ownership and not interrupted:
                interrupted = True
                raise KeyboardInterrupt("direct close interrupted")
            return original_close_record(kind, value)

        with mock.patch.object(
            session_module,
            "_close_owned_record",
            interrupt_once,
        ):
            with self.assertRaises(KeyboardInterrupt):
                lease.close()

        deadline = time.monotonic() + 1
        while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
            if time.monotonic() >= deadline:
                self.fail("interrupted lease close was not handed off")
            time.sleep(0.005)
        self.assertNotIn(
            ownership,
            session_module._PENDING_LEASE_CLOSE_FDS,
        )
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_tracked_claim_keyboard_interrupt_queues_exact_cleanup(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        ownership = (descriptor, object())
        store = self.module.SessionStore(Path("/unused"))
        store._tracked_claim_ownerships[descriptor] = ownership
        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        original_close_record = session_module._close_owned_record
        interrupted = False

        def interrupt_once(kind, value):
            nonlocal interrupted
            if value == ownership and not interrupted:
                interrupted = True
                raise KeyboardInterrupt("tracked close interrupted")
            return original_close_record(kind, value)

        with mock.patch.object(
            session_module,
            "_close_owned_record",
            interrupt_once,
        ):
            with self.assertRaises(KeyboardInterrupt):
                store._close_tracked_claim_descriptor(descriptor)

        deadline = time.monotonic() + 1
        while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
            if time.monotonic() >= deadline:
                self.fail("interrupted tracked close was not handed off")
            time.sleep(0.005)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_lease_finalizer_keyboard_interrupt_queues_exact_cleanup(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        lease = session_module.ClaimLease(
            self.module.SessionStore(Path("/unused")),
            "a" * 32,
            "b" * 64,
            descriptor,
        )
        ownership = (descriptor, lease._tracking_token)
        original_close_record = session_module._close_owned_record
        interrupted = False

        def interrupt_once(kind, value):
            nonlocal interrupted
            if value == ownership and not interrupted:
                interrupted = True
                raise KeyboardInterrupt("finalizer interrupted")
            return original_close_record(kind, value)

        with mock.patch.object(
            session_module,
            "_close_owned_record",
            interrupt_once,
        ):
            lease.__del__()

        deadline = time.monotonic() + 1
        while ownership in session_module._TRACKED_LEASE_OWNERSHIPS:
            if time.monotonic() >= deadline:
                self.fail("interrupted finalizer was not handed off")
            time.sleep(0.005)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_transaction_keyboard_interrupt_queues_exact_cleanup(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            session_module = sys.modules["audit_session"]
            original_close_record = session_module._close_owned_record
            interrupted_ownership = None

            def interrupt_once(kind, value):
                nonlocal interrupted_ownership
                if kind == "transaction" and interrupted_ownership is None:
                    interrupted_ownership = value
                    raise KeyboardInterrupt(
                        "transaction close interrupted"
                    )
                return original_close_record(kind, value)

            with mock.patch.object(
                session_module,
                "_close_owned_record",
                interrupt_once,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    with store._successor_transaction_lock(lease):
                        pass

            self.assertIsNotNone(interrupted_ownership)
            deadline = time.monotonic() + 1
            while (
                interrupted_ownership
                in session_module._TRACKED_TRANSACTION_OWNERSHIPS
            ):
                if time.monotonic() >= deadline:
                    self.fail(
                        "interrupted transaction was not handed off"
                    )
                time.sleep(0.005)
            self.assertNotIn(
                interrupted_ownership,
                session_module._PENDING_TRANSACTION_CLOSE_FDS,
            )
            with self.assertRaises(OSError):
                os.fstat(interrupted_ownership[0])
            lease.close()

    def test_cleanup_exit_system_exit_releases_and_restarts(self):
        session_module = sys.modules["audit_session"]
        descriptor = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        ownership = (descriptor, object())
        gate = session_module._DESCRIPTOR_OWNERSHIP_GATE
        original_exit = gate.exit_cleanup
        crashed_worker = None
        exited = False

        def exit_once(*args, **kwargs):
            nonlocal crashed_worker, exited
            if not exited:
                exited = True
                crashed_worker = threading.current_thread()
                raise SystemExit("cleanup exit interrupted")
            return original_exit(*args, **kwargs)

        session_module._TRACKED_LEASE_OWNERSHIPS.add(ownership)
        try:
            with mock.patch.object(gate, "exit_cleanup", exit_once):
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                deadline = time.monotonic() + 1
                while (
                    not exited
                    or gate._writer_intents
                    or gate._cleanup is not None
                    and gate._cleanup.locked()
                ):
                    if time.monotonic() >= deadline:
                        self.fail("cleanup exit crash wedged admission")
                    time.sleep(0.005)

            self.assertIsNotNone(crashed_worker)
            crashed_worker.join(timeout=1)
            self.assertFalse(crashed_worker.is_alive())
            self.assertIsNot(
                session_module._CLEANUP_THREAD,
                crashed_worker,
            )
            publisher = gate.try_enter_publication()
            self.assertIsNotNone(publisher)
            gate.exit_publication(publisher)
        finally:
            gate._writer_intents.clear()
            if gate._cleanup is not None and gate._cleanup.locked():
                gate._cleanup.release()
            session_module._TRACKED_LEASE_OWNERSHIPS.discard(
                ownership
            )
            session_module._PENDING_LEASE_CLOSE_FDS.discard(
                ownership
            )
            try:
                os.close(descriptor)
            except OSError:
                pass

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_child_cleanup_start_failure_can_be_retried(self):
        session_module = sys.modules["audit_session"]
        original_start = session_module.threading.Thread.start
        parent_pid = os.getpid()
        failed = False
        result_read, result_write = os.pipe()

        def fail_first_child_start(thread):
            nonlocal failed
            if os.getpid() != parent_pid and not failed:
                failed = True
                raise RuntimeError("child thread unavailable")
            return original_start(thread)

        with mock.patch.object(
            session_module.threading.Thread,
            "start",
            fail_first_child_start,
        ):
            child = os.fork()
            if child == 0:
                original_close = os.close
                original_close(result_read)
                descriptor = os.open(
                    "/dev/null",
                    os.O_RDONLY | os.O_CLOEXEC,
                )
                token = object()
                ownership = (descriptor, token)
                session_module._TRACKED_LEASE_OWNERSHIPS.add(
                    ownership
                )
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                session_module._schedule_pending_cleanup(
                    "lease",
                    ownership,
                )
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    try:
                        os.fstat(descriptor)
                    except OSError:
                        os.write(result_write, b"closed")
                        os._exit(0)
                    time.sleep(0.005)
                os.write(result_write, b"open")
                os._exit(1)

            os.close(result_write)
            outcome = os.read(result_read, 1024)
            _, status = os.waitpid(child, 0)
            os.close(result_read)

        self.assertEqual(outcome, b"closed")
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_child_snapshot_retries_one_shot_close_eio(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            lease = self.module.SessionStore(root).claim_lease(
                started.session
            )
            descriptor = lease._descriptor
            session_module = sys.modules["audit_session"]
            original_close = session_module.os.close
            original_owned_close = (
                session_module._close_owned_descriptor
            )
            parent_pid = os.getpid()
            failed = False
            result_read, result_write = os.pipe()

            def one_shot_child_eio(value):
                nonlocal failed
                if (
                    os.getpid() != parent_pid
                    and value == descriptor
                    and not failed
                ):
                    failed = True
                    raise OSError(errno.EIO, "transient child close failure")
                return original_owned_close(value)

            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                one_shot_child_eio,
            ):
                child = os.fork()
                if child == 0:
                    original_close(result_read)
                    try:
                        os.fstat(descriptor)
                    except OSError:
                        outcome = b"closed"
                    else:
                        outcome = b"open"
                    os.write(result_write, outcome)
                    os._exit(0)

                original_close(result_write)
                outcome = os.read(result_read, 1024)
                _, status = os.waitpid(child, 0)
                original_close(result_read)
            lease.close()

            self.assertEqual(outcome, b"closed")
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_child_persistent_snapshot_eio_retains_cleanup_authority(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            lease = self.module.SessionStore(root).claim_lease(
                started.session
            )
            descriptor = lease._descriptor
            token = lease._tracking_token
            ownership = (descriptor, token)
            session_module = sys.modules["audit_session"]
            original_close = session_module.os.close
            original_owned_close = (
                session_module._close_owned_descriptor
            )
            parent_pid = os.getpid()
            child_attempts = 0
            result_read, result_write = os.pipe()

            def two_child_eios(value):
                nonlocal child_attempts
                if os.getpid() != parent_pid and value == descriptor:
                    child_attempts += 1
                    if child_attempts <= 2:
                        raise OSError(
                            errno.EIO,
                            "persistent child close failure",
                        )
                return original_owned_close(value)

            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                two_child_eios,
            ):
                child = os.fork()
                if child == 0:
                    original_close(result_read)
                    session_module._schedule_pending_cleanup(
                        "lease",
                        ownership,
                    )
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline:
                        try:
                            os.fstat(descriptor)
                        except OSError:
                            os.write(result_write, b"closed")
                            os._exit(0)
                        time.sleep(0.005)
                    os.write(result_write, b"open")
                    os._exit(1)

                original_close(result_write)
                outcome = os.read(result_read, 1024)
                _, status = os.waitpid(child, 0)
                original_close(result_read)
            lease.close()

            self.assertEqual(outcome, b"closed")
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_dropped_unclosed_lease_is_finalized_and_recoverable(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            original_state = store.load(started.session)
            descriptor = lease._descriptor

            del lease
            gc.collect()

            with self.assertRaises(OSError):
                os.fstat(descriptor)
            terminal_state = {
                **original_state,
                "phase": "terminal",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }
            recovery = store.recover_claim(
                started.session,
                terminal_state,
            )
            self.assertEqual(recovery, "abandoned-claim-closed")
            session_module = sys.modules["audit_session"]
            self.assertEqual(
                session_module._TRACKED_LEASE_OWNERSHIPS,
                set(),
            )
            self.assertEqual(
                session_module._TRACKED_TRANSACTION_OWNERSHIPS,
                set(),
            )

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_fork_cannot_snapshot_transaction_between_open_and_tracking(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            session_module = sys.modules["audit_session"]
            original_open = session_module.os.open
            open_paused = threading.Event()
            release_open = threading.Event()
            transaction_entered = threading.Event()
            release_transaction = threading.Event()
            captured = []

            def paused_open(path, flags, *args, **kwargs):
                descriptor = original_open(path, flags, *args, **kwargs)
                if path == "transaction" and not captured:
                    captured.append(descriptor)
                    open_paused.set()
                    if not release_open.wait(2):
                        raise AssertionError(
                            "transaction open was not released"
                        )
                return descriptor

            def hold_transaction():
                with store._successor_transaction_lock(lease):
                    transaction_entered.set()
                    release_transaction.wait(2)

            child_result_read, child_result_write = os.pipe()
            with mock.patch.object(
                session_module.os,
                "open",
                paused_open,
            ):
                worker = threading.Thread(target=hold_transaction)
                worker.start()
                self.assertTrue(open_paused.wait(1))
                threading.Timer(0.1, release_open.set).start()
                child = os.fork()
                if child == 0:
                    os.close(child_result_read)
                    try:
                        os.fstat(captured[0])
                        outcome = b"child-fd-open"
                    except OSError:
                        outcome = b"child-fd-closed"
                    os.write(child_result_write, outcome)
                    os._exit(0)

                os.close(child_result_write)
                self.assertTrue(transaction_entered.wait(1))
                child_result = os.read(child_result_read, 1024)
                _, status = os.waitpid(child, 0)
                release_transaction.set()
                worker.join(timeout=1)
                os.close(child_result_read)
            lease.close()

            self.assertFalse(worker.is_alive())
            self.assertEqual(child_result, b"child-fd-closed")
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)

    @unittest.skipUnless(hasattr(os, "fork"), "requires os.fork")
    def test_fork_cannot_snapshot_transaction_during_physical_close(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            session_module = sys.modules["audit_session"]
            original_close = session_module.os.close
            original_owned_close = (
                session_module._close_owned_descriptor
            )
            transaction_entered = threading.Event()
            exit_transaction = threading.Event()
            close_paused = threading.Event()
            release_close = threading.Event()
            captured = []

            def paused_close(descriptor):
                if captured and descriptor == captured[0]:
                    close_paused.set()
                    if not release_close.wait(2):
                        raise AssertionError(
                            "transaction close was not released"
                        )
                return original_owned_close(descriptor)

            def hold_transaction():
                with store._successor_transaction_lock(lease):
                    captured.extend(
                        descriptor
                        for descriptor, _ in
                        session_module._TRACKED_TRANSACTION_OWNERSHIPS
                    )
                    transaction_entered.set()
                    exit_transaction.wait(2)

            child_result_read, child_result_write = os.pipe()
            with mock.patch.object(
                session_module,
                "_close_owned_descriptor",
                paused_close,
            ):
                worker = threading.Thread(target=hold_transaction)
                worker.start()
                self.assertTrue(transaction_entered.wait(1))
                exit_transaction.set()
                self.assertTrue(close_paused.wait(1))
                threading.Timer(0.1, release_close.set).start()
                child = os.fork()
                if child == 0:
                    original_close(child_result_read)
                    try:
                        os.fstat(captured[0])
                        outcome = b"child-fd-open"
                    except OSError:
                        outcome = b"child-fd-closed"
                    os.write(child_result_write, outcome)
                    os._exit(0)

                original_close(child_result_write)
                child_result = os.read(child_result_read, 1024)
                _, status = os.waitpid(child, 0)
                worker.join(timeout=1)
                original_close(child_result_read)
            lease.close()

            self.assertFalse(worker.is_alive())
            self.assertEqual(child_result, b"child-fd-closed")
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_active_continuation_lease_cannot_be_preempted_by_duplicate(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            write_response(started.response_path, code_response(started))
            original = self.module.SessionStore.claim_and_read
            acquired = threading.Event()
            release = threading.Event()
            captured = []

            def pause_after_claim(store, token, response_path):
                lease, raw = original(store, token, response_path)
                captured.append(lease)
                acquired.set()
                if not release.wait(2):
                    lease.close()
                    raise AssertionError("test did not release active lease")
                return lease, raw

            request = self.module.ContinueAudit(
                started.session,
                started.response_path,
            )
            with mock.patch.object(
                self.module.SessionStore,
                "claim_and_read",
                pause_after_claim,
            ), ThreadPoolExecutor(max_workers=1) as executor:
                first = executor.submit(self.runtime(root).advance, request)
                self.assertTrue(acquired.wait(1))
                before = time.monotonic()
                duplicate = self.runtime(root).advance(request)
                elapsed = time.monotonic() - before
                self.assertLess(elapsed, 1.0)
                self.assertEqual(duplicate.code, "SESSION_BUSY")
                self.assertEqual(
                    self.generation_count(root, started.session),
                    1,
                )
                release.set()
                result = first.result(timeout=2)

            self.assertIsInstance(result, self.module.NeedJudgment)
            self.assertEqual(result.kind, "reconciliation")
            self.assertEqual(self.generation_count(root, started.session), 2)
            self.assertEqual(len(captured), 1)
            self.assertTrue(captured[0].closed)

    def test_held_claim_lock_returns_session_busy_without_blocking(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            lease = store.claim_lease(started.session)
            try:
                run_id, digest = started.session.split(".", 1)
                transaction = (
                    root / run_id / "claims" / digest / "transaction"
                )
                self.assertEqual(
                    transaction.read_bytes(),
                    b"transaction-v1\n",
                )
                self.assertEqual(
                    stat.S_IMODE(transaction.stat().st_mode),
                    0o400,
                )
                before = time.monotonic()
                result = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        started.session,
                        started.response_path,
                    )
                )
                elapsed = time.monotonic() - before
            finally:
                lease.close()

            self.assertLess(elapsed, 1.0)
            self.assertEqual(result.code, "SESSION_BUSY")
            self.assertEqual(self.generation_count(root, started.session), 1)

    def test_post_publication_fsync_failure_releases_recoverable_lease(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            store = self.module.SessionStore(root)
            original_state = store.load(started.session)
            session_module = sys.modules["audit_session"]
            original_fsync = session_module.os.fsync
            calls = 0

            def fail_claims_fsync(descriptor):
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("injected post-publication fsync failure")
                return original_fsync(descriptor)

            with mock.patch.object(
                session_module.os,
                "fsync",
                fail_claims_fsync,
            ):
                with self.assertRaises(self.module.SessionIntegrityError):
                    store.claim_lease(started.session)

            terminal_state = {
                **original_state,
                "phase": "terminal",
                "nonce": "a" * 32,
                "response_name": f"{'b' * 32}.json",
            }
            recovery = store.recover_claim(
                started.session,
                terminal_state,
            )

            self.assertEqual(recovery, "abandoned-claim-closed")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_exact_code_deviation_ids_are_issued_for_matching(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            judgment = valid_code_judgment(packet_of(started))
            path_id = packet_of(started)["changed_path_ids"][0]
            judgment["deviations"] = [
                {
                    "path_id": path_id,
                    "line": 1,
                    "description": "The implementation uses a bounded path.",
                    "evidence_ids": ["source:CAPTURE-1"],
                    "reason": "This differs from the predicted surface.",
                }
            ]
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            packet = packet_of(result)
            self.assertEqual(packet["deviation_ids"], ["U1"])
            self.assertEqual(
                packet["deviations"][0]["deviation_id"],
                "U1",
            )
            self.assertIn("code-deviation:U1", packet["evidence_ids"])
            self.assertEqual(
                packet["response_schema"]["properties"]["judgment"][
                    "properties"
                ]["deviation_matches"]["items"]["properties"][
                    "deviation_id"
                ]["enum"],
                ["U1"],
            )

    def test_out_of_phase_reconciliation_generation_is_consumed_once(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            write_response(started.response_path, code_response(started))
            next_generation = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            unavailable = self.runtime(root).advance(
                self.module.ContinueAudit(
                    next_generation.session,
                    next_generation.response_path,
                )
            )

            self.assertEqual(unavailable.code, "OUT_OF_PHASE")
            count = self.generation_count(root, next_generation.session)
            duplicate = self.runtime(root).advance(
                self.module.ContinueAudit(
                    next_generation.session,
                    next_generation.response_path,
                )
            )
            self.assertIsInstance(duplicate, self.module.AuditStopped)
            self.assertEqual(
                self.generation_count(root, next_generation.session),
                count,
            )

    def test_out_of_phase_cleanup_contention_returns_session_busy(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            write_response(started.response_path, code_response(started))
            next_generation = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            session_module = sys.modules["audit_session"]

            with session_module._ownership_cleanup(
                "lease",
                (10_000_012, object()),
            ):
                before = time.monotonic()
                result = self.runtime(root).advance(
                    self.module.ContinueAudit(
                        next_generation.session,
                        next_generation.response_path,
                    )
                )
                elapsed = time.monotonic() - before

            self.assertLess(elapsed, 0.75)
            self.assertEqual(result.code, "SESSION_BUSY")

    def test_abandoned_claim_is_closed_on_later_continue(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            lease = self.module.SessionStore(root).claim_lease(
                started.session
            )
            lease.close()
            run = started.session.split(".", 1)[0]
            (
                root
                / run
                / "generations"
                / ".interrupted-staging-directory"
            ).mkdir()

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(self.generation_count(root, started.session), 2)
            run, original = started.session.split(".", 1)
            children = []
            for path in (root / run / "generations").iterdir():
                if path.name == original or path.name.startswith("."):
                    continue
                packet = json.loads(
                    (path / "packet.json").read_text(encoding="utf-8")
                )
                children.append(packet["kind"])
            self.assertEqual(children, ["terminal"])

    def test_qa_resolution_evidence_error_after_claim_is_terminal(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            head = git(repo, "rev-parse", "HEAD")
            narrative = repo / "qa-resolution-error.md"
            narrative.write_text(
                "<!-- qa-pr-evidence -->\n"
                "## QA evidence — ✅ PASS "
                f"<sub>(@ {head[:7]})</sub>\n",
                encoding="utf-8",
            )
            root = Path(temporary)
            started = self.start(
                repo,
                root,
                narrative_paths=(narrative,),
            )
            write_response(started.response_path, code_response(started))

            result = self.runtime(
                root,
                git_runner=FailingQaResolutionRunner(self.module),
            ).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "EVIDENCE_FAILURE")
            self.assertEqual(self.generation_count(root, started.session), 2)
            duplicate = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )
            self.assertEqual(duplicate.code, "DUPLICATE_RESPONSE")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_qa_marker_in_ledger_or_prior_report_does_not_count(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            head = git(repo, "rev-parse", "HEAD")
            report = (
                repo
                / ".notes/feature-proj-123/contract/v1/check-report.md"
            )
            report.write_text(
                "<!-- qa-pr-evidence -->\n"
                "## QA evidence — ✅ PASS "
                f"<sub>(@ {head})</sub>\n",
                encoding="utf-8",
            )
            root = Path(temporary)
            started = self.start(repo, root)
            write_response(started.response_path, code_response(started))

            result = self.runtime(root).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertFalse(packet_of(result)["acceptance_qa_exists"])

    def test_explicit_narrative_parent_symlink_outside_repo_is_rejected(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            secret = outside / "secret.md"
            secret.write_text("OUTSIDE_SECRET_SENTINEL\n", encoding="utf-8")
            alias = repo / "linked-outside"
            alias.symlink_to(outside, target_is_directory=True)

            result = self.runtime(root / "sessions").advance(
                self.module.StartAudit(
                    self.target(
                        repo,
                        narrative_paths=(alias / "secret.md",),
                    )
                )
            )

            self.assertIsInstance(result, self.module.AuditStopped)
            self.assertEqual(result.code, "EVIDENCE_FAILURE")
            self.assertNotIn("OUTSIDE_SECRET_SENTINEL", result.reason)
            self.assertEqual(
                secret.read_text(encoding="utf-8"),
                "OUTSIDE_SECRET_SENTINEL\n",
            )

    def test_qa_heading_requires_a_unique_seven_character_head_prefix(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            head = git(repo, "rev-parse", "HEAD")
            for name, marker, reference, expected, binary in (
                ("marker-only", True, None, False, False),
                ("short", True, head[:6], False, False),
                ("stale", True, "0" * 12, False, False),
                ("head", True, head[:7], True, False),
                ("full-head", True, head, True, False),
                ("non-utf8", True, head[:12], False, True),
            ):
                with self.subTest(name=name):
                    narrative = repo / f"{name}-qa.md"
                    text = (
                        ("<!-- qa-pr-evidence -->\n" if marker else "")
                        + (
                            "## QA evidence — ✅ PASS "
                            f"<sub>(@ {reference})</sub>\n"
                            if reference is not None
                            else ""
                        )
                    ).encode("utf-8")
                    narrative.write_bytes(
                        text + (b"\xff" if binary else b"")
                    )
                    child_root = Path(temporary) / name
                    started = self.start(
                        repo,
                        child_root,
                        narrative_paths=(narrative,),
                    )
                    write_response(
                        started.response_path,
                        code_response(started),
                    )
                    result = self.runtime(child_root).advance(
                        self.module.ContinueAudit(
                            started.session,
                            started.response_path,
                        )
                    )
                    self.assertEqual(
                        packet_of(result)["acceptance_qa_exists"],
                        expected,
                    )

    def test_qa_short_sha_must_resolve_to_one_git_object(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            head = git(repo, "rev-parse", "HEAD")
            narrative = repo / "ambiguous-qa.md"
            narrative.write_text(
                "<!-- qa-pr-evidence -->\n"
                "## QA evidence — ✅ PASS "
                f"<sub>(@ {head[:7]})</sub>\n",
                encoding="utf-8",
            )
            runner = AmbiguousShaRunner(self.module, head)
            root = Path(temporary)
            started = self.runtime(root, git_runner=runner).advance(
                self.module.StartAudit(
                    self.target(repo, narrative_paths=(narrative,))
                )
            )
            write_response(started.response_path, code_response(started))

            result = self.runtime(root, git_runner=runner).advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            packet = packet_of(result)
            self.assertFalse(packet["acceptance_qa_exists"])
            self.assertEqual(runner.disambiguations, [head[:7]])
            self.assertEqual(
                packet["runtime_facts"]["qa_sha_resolution"][
                    "candidates"
                ][0]["object_ids"],
                [
                    head,
                    head[:7] + "f" * 33,
                ],
            )

    def test_deadline_is_rechecked_after_qa_sha_resolution(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            head = git(repo, "rev-parse", "HEAD")
            narrative = repo / "qa.md"
            narrative.write_text(
                "<!-- qa-pr-evidence -->\n"
                "## QA evidence — ✅ PASS "
                f"<sub>(@ {head[:7]})</sub>\n",
                encoding="utf-8",
            )
            clock = FakeClock()
            runner = DeadlineAdvancingRunner(self.module, clock)
            root = Path(temporary)
            runtime = self.runtime(root, clock=clock, git_runner=runner)
            started = runtime.advance(
                self.module.StartAudit(
                    self.target(repo, narrative_paths=(narrative,)),
                    deadline_seconds=60,
                )
            )
            write_response(started.response_path, code_response(started))

            result = runtime.advance(
                self.module.ContinueAudit(
                    started.session,
                    started.response_path,
                )
            )

            self.assertEqual(result.code, "DEADLINE_EXPIRED")
            self.assertEqual(self.generation_count(root, started.session), 2)

    def test_ledger_parser_requires_sequential_ids_and_all_seven_fields(self):
        valid = (
            "# Execution Ledger\n\n"
            "## D1 — 2026-07-23T13:03:00Z — parent\n\n"
            "- Affected clauses: R2\n"
            "- Discovered fact: A helper exists.\n"
            "- Actual approach: Reuse it.\n"
            "- Reason for proceeding: The contract remains unchanged.\n"
            "- Alternatives considered: Duplicate it; rejected.\n"
            "- Risk delta: None.\n"
            "- Verification evidence: src/pricing.py:5.\n"
        )
        entries = self.reconciliation.parse_execution_ledger(
            valid.encode("utf-8")
        )
        self.assertEqual(entries[0].ledger_id, "D1")
        for mutation in (
            valid.replace("D1", "D2", 1),
            valid.replace("- Risk delta: None.\n", ""),
            valid.replace("- Risk delta:", "- Unknown field:"),
            valid.replace("src/pricing.py:5.", ""),
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(
                    self.reconciliation.ReconciliationError
                ):
                    self.reconciliation.parse_execution_ledger(
                        mutation.encode("utf-8")
                    )

    def test_ledger_parser_reuses_closed_canonical_probe_parser(self):
        probe = (
            '{"kind":"python-call-v1","module":"src.pricing",'
            '"callable":"validate_percentage","cases":'
            '[{"args":[0],"expect":"returns"}]}'
        )
        ledger = (
            "# Execution Ledger\n\n"
            "## D1 — 2026-07-23T13:03:00Z — parent\n\n"
            "- Affected clauses: R2\n"
            "- Discovered fact: A helper exists.\n"
            "- Actual approach: Reuse it.\n"
            "- Reason for proceeding: The contract remains unchanged.\n"
            "- Alternatives considered: Duplicate it; rejected.\n"
            "- Risk delta: None.\n"
            "- Verification evidence: src/pricing.py:5.\n"
            f"- Replay probe: `{probe}`\n"
        )

        parsed = self.reconciliation.parse_execution_ledger(
            ledger.encode("utf-8")
        )

        self.assertEqual(parsed[0].probe.module, "src.pricing")
        noncanonical = ledger.replace(
            probe,
            probe.replace('","module"', '", "module"'),
        )
        with self.assertRaises(self.reconciliation.ReconciliationError):
            self.reconciliation.parse_execution_ledger(
                noncanonical.encode("utf-8")
            )
        with self.assertRaises(self.reconciliation.ReconciliationError):
            self.reconciliation.parse_execution_ledger(
                ledger.replace(
                    '"kind":"python-call-v1"',
                    '"kind":"shell","argv":["true"]',
                ).encode("utf-8")
            )


if __name__ == "__main__":
    unittest.main()
