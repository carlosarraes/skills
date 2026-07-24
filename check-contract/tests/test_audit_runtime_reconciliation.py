import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

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
        return len(list((Path(root) / run / "generations").iterdir()))

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
