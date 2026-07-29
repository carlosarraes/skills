import json
import tempfile
import unittest
from pathlib import Path

from runtime_fixtures import materialized_repo, packet_of
from test_audit_runtime_reconciliation import (
    code_response,
    load_modules,
    valid_code_judgment,
    write_response,
)
from test_audit_runtime_start import FakeClock, git


class FailingBaseSourceRunner:
    def __init__(self, module, base, clock):
        self.module = module
        self.base = base
        self.delegate = module.LocalGitRunner(clock)

    def run(self, args, *, cwd, deadline, output_limit=None):
        if args == ["show", f"{self.base}:src/pricing.py"]:
            return type(
                "IncompleteResult",
                (),
                {"stdout": b"", "truncated": False, "timed_out": True},
            )()
        return self.delegate.run(
            args,
            cwd=cwd,
            deadline=deadline,
            output_limit=output_limit,
        )


class RuntimeSemanticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, _ = load_modules()

    def target(self, repo):
        return self.module.AuditTarget(
            repo=repo,
            branch="feature/proj-123",
            ticket="PROJ-123",
        )

    def start(self, repo, root):
        return self.module.AuditRuntime(
            session_root=root,
            clock=FakeClock(),
        ).advance(self.module.StartAudit(self.target(repo)))

    def bound_judgment(self, packet):
        judgment = valid_code_judgment(packet)
        judgment["semantic_generation"] = packet["semantics"]["generation"]
        judgment["chronology_generation"] = packet["chronology"]["generation"]
        return judgment

    def issue_reconciliation(
        self, repo, root, judgment=None, clause_statuses=None
    ):
        runtime = self.module.AuditRuntime(
            session_root=root,
            clock=FakeClock(),
        )
        started = runtime.advance(self.module.StartAudit(self.target(repo)))
        packet = packet_of(started)
        if judgment is None:
            judgment = self.bound_judgment(packet)
        for clause_id, status in (clause_statuses or {}).items():
            judgment["clauses"][clause_id]["status"] = status
        write_response(
            started.response_path,
            code_response(
                started,
                judgment=judgment,
            ),
        )
        return runtime.advance(
            self.module.ContinueAudit(started.session, started.response_path)
        )

    def reconciliation_response(self, issued, deviation_id=None):
        packet = packet_of(issued)
        entry = packet["ledger_entries"][0]
        return {
            "schema_version": 1,
            "session": issued.session,
            "nonce": issued.nonce,
            "packet_sha256": issued.packet_sha256,
            "kind": "reconciliation",
            "judgment": {
                "semantic_generation": packet["semantics"]["generation"],
                "chronology_generation": packet["chronology"]["generation"],
                "ledger_entries": {
                    "D1": {
                        "status": "VERIFIED",
                        "evidence_ids": [entry["evidence_id"]],
                        "reason": "D1 is verified by issued evidence.",
                    }
                },
                "deviation_matches": (
                    []
                    if deviation_id is None
                    else [{"deviation_id": deviation_id, "ledger_id": "D1"}]
                ),
                "contract_obsolete": {
                    "value": False,
                    "evidence_ids": [],
                    "reason": "The approved contract remains authoritative.",
                },
                "probe_id": None,
            },
        }

    def test_code_packet_semantics_are_canonical_closed_and_deterministic(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            packets = [
                packet_of(self.start(repo, Path(root)))
                for root in (first, second)
            ]

        semantic = packets[0]["semantics"]
        self.assertEqual(semantic, packets[1]["semantics"])
        self.assertEqual(
            set(semantic),
            {
                "schema_version",
                "generation",
                "clause_ownership",
                "exact_predicate",
                "status_meanings",
                "contract_boundary",
                "reuse",
                "ledger_reconciliation",
                "stable_id_aliases",
                "issued_facts",
            },
        )
        self.assertEqual(
            semantic["clause_ownership"]["contract_fidelity"],
            ["O", "B", "N", "I", "C", "A"],
        )
        self.assertEqual(
            semantic["clause_ownership"]["independent_axes"],
            {"R": "REUSE", "S": "SURFACE", "K": "COMPLEXITY"},
        )
        self.assertEqual(
            semantic["status_meanings"]["upper_bound_breach"],
            "EXCEEDED",
        )
        self.assertEqual(
            semantic["status_meanings"]["non_demonstrative_acceptance"],
            "INDETERMINATE",
        )
        self.assertEqual(
            semantic["stable_id_aliases"],
            {"K-RUNTIME-DEPENDENCIES": "K-DEPENDENCIES"},
        )

    def test_packets_use_one_canonical_dependency_clause_id(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            packet = packet_of(self.start(repo, Path(temporary)))

        self.assertIn("K-DEPENDENCIES", packet["clause_ids"])
        self.assertNotIn("K-RUNTIME-DEPENDENCIES", packet["clause_ids"])

    def test_protocol_documents_legacy_dependency_id_normalization(self):
        protocol = (
            Path(__file__).parents[2]
            / "change-contract"
            / "references"
            / "contract-protocol.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "normalize legacy `K-RUNTIME-DEPENDENCIES` to canonical "
            "`K-DEPENDENCIES`",
            " ".join(protocol.split()),
        )

    def test_documented_helper_chronology_predates_affected_implementation(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            packet = packet_of(self.start(repo, Path(temporary)))
            helper_commit = git(repo, "rev-parse", "HEAD^")
            implementation_commit = git(repo, "rev-parse", "HEAD")

        chronology = packet["chronology"]
        helper = next(
            item
            for item in chronology["helper_facts"]
            if item["name"] == "_validate_percentage"
        )
        self.assertEqual(chronology["status"], "DETERMINATE")
        self.assertFalse(helper["existed_at_approval_base"])
        self.assertEqual(helper["introduced_commit"], helper_commit)
        self.assertEqual(
            helper["affected_implementation_commits"],
            [implementation_commit],
        )
        self.assertEqual(
            helper["relation"],
            "INTRODUCED_BEFORE_AFFECTED_IMPLEMENTATION",
        )
        self.assertEqual(len(helper_commit), 40)
        self.assertEqual(len(implementation_commit), 40)

    def test_response_must_echo_semantic_and_chronology_generations(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            packet = packet_of(started)
            judgment = valid_code_judgment(packet)
            judgment.pop("semantic_generation")
            judgment.pop("chronology_generation")
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )
            stopped = self.module.AuditRuntime(
                session_root=root,
                clock=FakeClock(),
            ).advance(
                self.module.ContinueAudit(started.session, started.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_exact_zero_cap_breach_rejects_unmet(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            packet = packet_of(started)
            fact = packet["semantics"]["issued_facts"]["clause_statuses"][
                "K-ABSTRACTIONS"
            ]
            self.assertEqual(fact["status"], "EXCEEDED")
            self.assertEqual(fact["cap"], 0)
            judgment = self.bound_judgment(packet)
            judgment["clauses"]["K-ABSTRACTIONS"]["status"] = "UNMET"
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )
            stopped = self.module.AuditRuntime(
                session_root=root,
                clock=FakeClock(),
            ).advance(
                self.module.ContinueAudit(started.session, started.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_used_helper_cannot_be_classified_as_bypassed(self):
        with materialized_repo(
            "contract-violated-summary", "target-b"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            packet = packet_of(started)
            helper = next(
                item
                for item in packet["semantics"]["issued_facts"]["helpers"]
                if item["name"] == "_validate_percentage"
            )
            self.assertEqual(helper["use_status"], "USED")
            path_id = helper["used_by_path_ids"][0]
            judgment = self.bound_judgment(packet)
            judgment["path_assessments"][path_id]["reuse_items"] = [
                {
                    "kind": "BYPASSED",
                    "helper_fact_ids": [helper["fact_id"]],
                    "evidence_ids": helper["evidence_ids"],
                    "reason": "The helper was bypassed.",
                }
            ]
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )
            stopped = self.module.AuditRuntime(
                session_root=root,
                clock=FakeClock(),
            ).advance(
                self.module.ContinueAudit(started.session, started.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_same_file_helper_use_is_issued_as_used(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            packet = packet_of(self.start(repo, Path(temporary)))

        helper = next(
            item
            for item in packet["semantics"]["issued_facts"]["helpers"]
            if item["name"] == "_DiscountCalculation"
        )
        checkout = next(
            item["path_id"]
            for item in packet["changed_paths"]
            if item["path"] == "src/checkout.py"
        )
        self.assertEqual(helper["use_status"], "USED")
        self.assertEqual(helper["used_by_path_ids"], [checkout])

    def test_test_and_unqualified_calls_do_not_become_helper_use_facts(self):
        cases = (
            (
                "tests/test_checkout.py",
                "\n_validate_percentage(50)\n",
            ),
            (
                "src/checkout.py",
                "\ndef semantic_probe():\n    return _validate_percentage(50)\n",
            ),
        )
        for path, addition in cases:
            with self.subTest(path=path), materialized_repo(
                "contract-compliant-overengineered"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                target = repo / path
                target.write_text(
                    target.read_text(encoding="utf-8") + addition,
                    encoding="utf-8",
                )
                git(repo, "add", path)
                git(repo, "commit", "-m", "test: add unrelated call")
                packet = packet_of(self.start(repo, Path(temporary)))

            helper = next(
                item
                for item in packet["semantics"]["issued_facts"]["helpers"]
                if item["name"] == "_validate_percentage"
            )
            self.assertEqual(helper["use_status"], "NOT_USED")
            self.assertEqual(helper["used_by_path_ids"], [])

    def test_relative_import_helper_use_is_qualified_and_issued(self):
        with materialized_repo(
            "contract-violated-summary", "target-b"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            checkout = repo / "src/checkout.py"
            checkout.write_text(
                checkout.read_text(encoding="utf-8").replace(
                    "from src.pricing import", "from .pricing import"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "src/checkout.py")
            git(repo, "commit", "-m", "test: use relative helper import")
            packet = packet_of(self.start(repo, Path(temporary)))

        helper = next(
            item
            for item in packet["semantics"]["issued_facts"]["helpers"]
            if item["name"] == "_validate_percentage"
        )
        self.assertEqual(helper["use_status"], "USED")

    def test_full_head_search_issues_unchanged_helper_for_bypass(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.name", "Semantic Test")
            git(repo, "config", "user.email", "semantic@example.invalid")
            (repo / "src").mkdir()
            helper_source = "def shared_helper(value):\n    return value\n"
            consumer_source = "VALUE = 1\n"
            (repo / "src/helpers.py").write_text(
                helper_source, encoding="utf-8"
            )
            (repo / "src/consumer.py").write_text(
                consumer_source, encoding="utf-8"
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "test: establish helper")
            base = git(repo, "rev-parse", "HEAD")
            consumer_source = "VALUE = 2\n"
            (repo / "src/consumer.py").write_text(
                consumer_source, encoding="utf-8"
            )
            git(repo, "add", "src/consumer.py")
            git(repo, "commit", "-m", "test: change consumer")
            head = git(repo, "rev-parse", "HEAD")
            captured = {
                "changed_paths": [
                    {
                        "path_id": "P1",
                        "status": "M",
                        "path": "src/consumer.py",
                        "old_path": "src/consumer.py",
                        "head_blob": consumer_source,
                    }
                ],
                "evidence": {
                    "reuse:SEARCH-1": {
                        "results": [
                            {
                                "path": "src/helpers.py",
                                "line": 1,
                                "text": "def shared_helper(value):",
                            }
                        ]
                    }
                },
            }
            clock = FakeClock()
            semantics = __import__("audit_semantics")
            model = semantics._source_model(
                {
                    "repository_root": repo,
                    "base_sha": base,
                    "head_sha": head,
                },
                captured,
                self.module.LocalGitRunner(clock),
                1300.0,
            )

        helper = next(
            item
            for item in model["helpers"]
            if item["name"] == "shared_helper"
        )
        self.assertIsNone(helper["definition_path_id"])
        self.assertTrue(helper["existed_at_approval_base"])
        self.assertEqual(helper["use_status"], "NOT_USED")
        self.assertEqual(helper["evidence_ids"], ["reuse:SEARCH-1"])

        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            packet = packet_of(self.start(repo, Path(temporary)))
        packet["semantics"]["issued_facts"]["helpers"] = [helper]
        path_id = packet["changed_path_ids"][0]
        judgment = self.bound_judgment(packet)
        judgment["path_assessments"][path_id]["reuse_items"] = [
            {
                "kind": "BYPASSED",
                "helper_fact_ids": [helper["fact_id"]],
                "evidence_ids": helper["evidence_ids"],
                "reason": "The unchanged compatible helper was bypassed.",
            }
        ]
        parsed = self.module.validate_code_judgment(packet, judgment)
        self.assertEqual(parsed.path_assessments[0].reuse_items[0].kind, "BYPASSED")

    def test_used_helper_cannot_be_bypassed_by_omitting_its_fact_id(self):
        with materialized_repo(
            "contract-violated-summary", "target-b"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            packet = packet_of(started)
            helper = next(
                item
                for item in packet["semantics"]["issued_facts"]["helpers"]
                if item["name"] == "_validate_percentage"
            )
            path_id = helper["used_by_path_ids"][0]
            judgment = self.bound_judgment(packet)
            judgment["path_assessments"][path_id]["reuse_items"] = [
                {
                    "kind": "BYPASSED",
                    "helper_fact_ids": [],
                    "evidence_ids": ["reuse:SEARCH-1"],
                    "reason": "The used helper was bypassed.",
                }
            ]
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )
            stopped = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            ).advance(
                self.module.ContinueAudit(started.session, started.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_verified_ledger_match_is_limited_to_declared_bounded_clauses(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            issued = self.issue_reconciliation(
                repo,
                Path(temporary),
                clause_statuses={"K-ABSTRACTIONS": "EXCEEDED"},
            )
            packet = packet_of(issued)

        self.assertEqual(
            packet["ledger_entries"][0]["affected_clause_ids"],
            ["R2", "S1", "K-ABSTRACTIONS"],
        )
        self.assertEqual(
            {
                item["stable_clause_id"]
                for item in packet["deviation_semantics"]
            },
            {"K-ABSTRACTIONS"},
        )

    def test_verified_match_rejects_clause_omitted_by_d1(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            ledger = repo / (
                ".notes/feature-proj-123/contract/v1/execution-ledger.md"
            )
            ledger.write_bytes(
                ledger.read_bytes().replace(
                    b"R2, S1, K-ABSTRACTIONS", b"R2, S1"
                )
            )
            root = Path(temporary)
            issued = self.issue_reconciliation(
                repo,
                root,
                clause_statuses={"K-ABSTRACTIONS": "EXCEEDED"},
            )
            packet = packet_of(issued)
            deviation_id = next(
                item["deviation_id"]
                for item in packet["deviation_semantics"]
                if item["stable_clause_id"] == "K-ABSTRACTIONS"
            )
            write_response(
                issued.response_path,
                self.reconciliation_response(issued, deviation_id),
            )
            stopped = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            ).advance(
                self.module.ContinueAudit(issued.session, issued.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_verified_match_rejects_wrong_clause_in_same_family(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            ledger = repo / (
                ".notes/feature-proj-123/contract/v1/execution-ledger.md"
            )
            ledger.write_bytes(
                ledger.read_bytes().replace(
                    b"K-ABSTRACTIONS", b"K-CONFIGURATION"
                )
            )
            root = Path(temporary)
            issued = self.issue_reconciliation(
                repo,
                root,
                clause_statuses={"K-ABSTRACTIONS": "EXCEEDED"},
            )
            semantic = next(
                item
                for item in packet_of(issued)["deviation_semantics"]
                if item["stable_clause_id"] == "K-ABSTRACTIONS"
            )
            write_response(
                issued.response_path,
                self.reconciliation_response(
                    issued, semantic["deviation_id"]
                ),
            )
            stopped = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            ).advance(
                self.module.ContinueAudit(issued.session, issued.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_boundary_changed_bounded_family_cannot_be_legalized(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            started = self.start(repo, root)
            packet = packet_of(started)
            judgment = self.bound_judgment(packet)
            clause = judgment["clauses"]["K-ABSTRACTIONS"]
            clause["status"] = "EXCEEDED"
            clause["contract_boundary_changed"] = True
            clause["evidence_ids"] = []
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )
            issued = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            ).advance(
                self.module.ContinueAudit(started.session, started.response_path)
            )
            semantic = next(
                item
                for item in packet_of(issued)["deviation_semantics"]
                if item["stable_clause_id"] == "K-ABSTRACTIONS"
            )
            self.assertEqual(semantic["boundedness"], "UNBOUNDED")
            write_response(
                issued.response_path,
                self.reconciliation_response(
                    issued, semantic["deviation_id"]
                ),
            )
            stopped = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            ).advance(
                self.module.ContinueAudit(issued.session, issued.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_bounded_generic_path_deviations_match_declared_family(self):
        for source_kind in ("surface", "explicit"):
            with self.subTest(source_kind=source_kind), materialized_repo(
                "documented-drift"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                started = self.start(repo, root)
                packet = packet_of(started)
                checkout = next(
                    item["path_id"]
                    for item in packet["changed_paths"]
                    if item["path"] == "src/checkout.py"
                )
                judgment = self.bound_judgment(packet)
                if source_kind == "surface":
                    judgment["path_assessments"][checkout]["surface"] = {
                        "status": "EXCEEDED",
                        "evidence_ids": ["source:CAPTURE-1"],
                        "reason": "The implementation path differs.",
                    }
                else:
                    judgment["deviations"] = [
                        {
                            "path_id": checkout,
                            "line": 10,
                            "description": "The implementation path differs.",
                            "evidence_ids": ["surface:S1"],
                            "reason": "The issued surface evidence proves it.",
                        }
                    ]
                write_response(
                    started.response_path,
                    code_response(started, judgment=judgment),
                )
                issued = self.module.AuditRuntime(
                    session_root=root, clock=FakeClock()
                ).advance(
                    self.module.ContinueAudit(
                        started.session, started.response_path
                    )
                )
                semantic = next(
                    item
                    for item in packet_of(issued)["deviation_semantics"]
                    if item["stable_clause_family"] == "S"
                )
                self.assertEqual(
                    semantic["stable_clause_id"],
                    None if source_kind == "surface" else "S1",
                )
                self.assertEqual(semantic["boundedness"], "BOUNDED")
                write_response(
                    issued.response_path,
                    self.reconciliation_response(
                        issued, semantic["deviation_id"]
                    ),
                )
                complete = self.module.AuditRuntime(
                    session_root=root, clock=FakeClock()
                ).advance(
                    self.module.ContinueAudit(
                        issued.session, issued.response_path
                    )
                )

            self.assertIsInstance(complete, self.module.AuditComplete)

    def test_explicit_public_evidence_cannot_hide_behind_k_family(self):
        for evidence_ids, stable_id in (
            (["complexity:K-PUBLIC-INTERFACES"], "K-PUBLIC-INTERFACES"),
            (
                [
                    "complexity:K-ABSTRACTIONS",
                    "complexity:K-PUBLIC-INTERFACES",
                ],
                None,
            ),
        ):
            with self.subTest(evidence_ids=evidence_ids), materialized_repo(
                "documented-drift"
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                started = self.start(repo, root)
                packet = packet_of(started)
                judgment = self.bound_judgment(packet)
                judgment["deviations"] = [
                    {
                        "path_id": packet["changed_path_ids"][0],
                        "line": 1,
                        "description": "A public interface was added.",
                        "evidence_ids": evidence_ids,
                        "reason": "The issued public evidence proves it.",
                    }
                ]
                write_response(
                    started.response_path,
                    code_response(started, judgment=judgment),
                )
                issued = self.module.AuditRuntime(
                    session_root=root, clock=FakeClock()
                ).advance(
                    self.module.ContinueAudit(
                        started.session, started.response_path
                    )
                )
                semantic = packet_of(issued)["deviation_semantics"][0]
                self.assertEqual(semantic["stable_clause_id"], stable_id)
                self.assertEqual(semantic["boundedness"], "UNBOUNDED")
                write_response(
                    issued.response_path,
                    self.reconciliation_response(
                        issued, semantic["deviation_id"]
                    ),
                )
                stopped = self.module.AuditRuntime(
                    session_root=root, clock=FakeClock()
                ).advance(
                    self.module.ContinueAudit(
                        issued.session, issued.response_path
                    )
                )

            self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_verified_match_rejects_public_contract_deviation(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            ledger = repo / (
                ".notes/feature-proj-123/contract/v1/execution-ledger.md"
            )
            ledger.write_bytes(
                ledger.read_bytes().replace(
                    b"R2, S1, K-ABSTRACTIONS",
                    b"K-PUBLIC-INTERFACES",
                )
            )
            root = Path(temporary)
            runtime = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            )
            started = runtime.advance(self.module.StartAudit(self.target(repo)))
            code_packet = packet_of(started)
            judgment = self.bound_judgment(code_packet)
            judgment["clauses"]["K-PUBLIC-INTERFACES"]["status"] = "EXCEEDED"
            write_response(
                started.response_path,
                code_response(started, judgment=judgment),
            )
            issued = runtime.advance(
                self.module.ContinueAudit(started.session, started.response_path)
            )
            packet = packet_of(issued)
            deviation_id = next(
                item["deviation_id"]
                for item in packet["deviation_semantics"]
                if item["stable_clause_id"] == "K-PUBLIC-INTERFACES"
            )
            write_response(
                issued.response_path,
                self.reconciliation_response(issued, deviation_id),
            )
            stopped = runtime.advance(
                self.module.ContinueAudit(issued.session, issued.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_verified_public_contract_ledger_is_rejected_without_a_match(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            ledger = repo / (
                ".notes/feature-proj-123/contract/v1/execution-ledger.md"
            )
            ledger.write_bytes(
                ledger.read_bytes().replace(
                    b"R2, S1, K-ABSTRACTIONS",
                    b"K-PUBLIC-INTERFACES",
                )
            )
            root = Path(temporary)
            issued = self.issue_reconciliation(repo, root)
            write_response(
                issued.response_path,
                self.reconciliation_response(issued),
            )
            stopped = self.module.AuditRuntime(
                session_root=root, clock=FakeClock()
            ).advance(
                self.module.ContinueAudit(issued.session, issued.response_path)
            )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")

    def test_semantic_sections_are_bound_into_packet_hash(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            started = self.start(repo, Path(temporary))
            packet = packet_of(started)
            canonical = (
                json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()

        import hashlib

        self.assertEqual(hashlib.sha256(canonical).hexdigest(), started.packet_sha256)

    def test_all_v3_code_packets_issue_the_golden_decision_facts(self):
        cases = (
            ("contract-compliant-overengineered", "target", "NOT_USED", 2),
            ("contract-violated-summary", "target-b", "USED", 1),
            ("documented-drift", "target", "USED", 1),
        )
        for scenario, target, helper_use, abstraction_count in cases:
            with self.subTest(scenario=scenario), materialized_repo(
                scenario, target
            ) as repo, tempfile.TemporaryDirectory() as temporary:
                packet = packet_of(self.start(repo, Path(temporary)))
                helper = next(
                    item
                    for item in packet["semantics"]["issued_facts"]["helpers"]
                    if item["name"] == "_validate_percentage"
                )
                self.assertEqual(helper["use_status"], helper_use)
                abstraction = packet["semantics"]["issued_facts"][
                    "clause_statuses"
                ]["K-ABSTRACTIONS"]
                self.assertEqual(abstraction["status"], "EXCEEDED")
                self.assertEqual(abstraction["actual"], abstraction_count)
                self.assertEqual(
                    packet["semantics"]["status_meanings"][
                        "non_demonstrative_acceptance"
                    ],
                    "INDETERMINATE",
                )
                self.assertEqual(len(packet["chronology"]["generation"]), 64)

    def test_merge_chronology_is_explicit_unknown_and_deterministic(self):
        with materialized_repo(
            "contract-compliant-overengineered"
        ) as repo, tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            branch = git(repo, "branch", "--show-current")
            git(repo, "checkout", "-b", "semantic-side")
            (repo / "src/semantic_side.py").write_text(
                "SIDE = True\n", encoding="utf-8"
            )
            git(repo, "add", "src/semantic_side.py")
            git(repo, "commit", "-m", "test: add semantic side")
            git(repo, "checkout", branch)
            (repo / "src/semantic_main.py").write_text(
                "MAIN = True\n", encoding="utf-8"
            )
            git(repo, "add", "src/semantic_main.py")
            git(repo, "commit", "-m", "test: add semantic main")
            git(repo, "merge", "--no-ff", "semantic-side", "-m", "test: merge semantics")

            values = [
                packet_of(self.start(repo, Path(root)))["chronology"]
                for root in (first, second)
            ]

        self.assertEqual(values[0], values[1])
        self.assertEqual(values[0]["status"], "INDETERMINATE")
        self.assertEqual(
            values[0]["unknown_reason"], "MERGE_OR_AMBIGUOUS_ANCESTRY"
        )
        self.assertRegex(values[0]["approval_base_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(values[0]["head_sha"], r"^[0-9a-f]{40}$")

    def test_incomplete_base_source_never_invents_an_exact_budget_fact(self):
        with materialized_repo(
            "documented-drift"
        ) as repo, tempfile.TemporaryDirectory() as temporary:
            base = git(repo, "rev-parse", "7aa39139^{commit}")
            clock = FakeClock()
            started = self.module.AuditRuntime(
                session_root=Path(temporary),
                clock=clock,
                git_runner=FailingBaseSourceRunner(self.module, base, clock),
            ).advance(self.module.StartAudit(self.target(repo)))
            packet = packet_of(started)

        self.assertNotIn(
            "K-ABSTRACTIONS",
            packet["semantics"]["issued_facts"]["clause_statuses"],
        )
        helper = next(
            item
            for item in packet["chronology"]["helper_facts"]
            if item["name"] == "_validate_percentage"
        )
        self.assertIsNone(helper["existed_at_approval_base"])
        self.assertEqual(helper["relation"], "INDETERMINATE")


if __name__ == "__main__":
    unittest.main()
