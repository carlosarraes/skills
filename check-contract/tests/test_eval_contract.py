import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
EVALS = ROOT / "evals" / "evals.json"
MANIFEST = ROOT / "evals" / "fixture-manifest.json"
MATERIALIZER = ROOT / "evals" / "materialize_fixture.py"
ASSERTIONS_PATH = ROOT / "evals" / "assertion_contract.py"
SEMANTIC_ORACLE_PATH = ROOT / "evals" / "semantic_oracle.py"
SPEC = importlib.util.spec_from_file_location("check_assertions", ASSERTIONS_PATH)
ASSERTIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSERTIONS)
PREFLIGHT_PATH = ROOT / "evals" / "runner_preflight.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "check_runner_preflight", PREFLIGHT_PATH
)
PREFLIGHT = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(PREFLIGHT)
RUNNER_PATH = ROOT / "evals" / "isolated_runner.py"
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "check_isolated_runner", RUNNER_PATH
)
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
sys.path.insert(0, str(ROOT / "evals"))
RUNNER_SPEC.loader.exec_module(RUNNER)
sys.path.pop(0)
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from audit_domain import load_rules  # noqa: E402
sys.path.pop(0)
RULES = (
    ROOT.parent
    / "change-contract"
    / "references"
    / "contract-check-rules.json"
)
CONTRACT_ROOT = Path(".notes/feature-proj-123/contract")
VERSION = CONTRACT_ROOT / "v1"
DOCUMENTED_DRIFT_OVERLAY = (
    ROOT
    / "evals"
    / "fixtures"
    / "documented-drift"
    / "overlay"
)
REPLAY_PROBE = {
    "kind": "python-call-v1",
    "module": "src.pricing",
    "callable": "_validate_percentage",
    "cases": [
        {"args": [0], "expect": "returns"},
        {"args": [100], "expect": "returns"},
        {
            "args": [-1],
            "expect": "raises",
            "exception": "ValueError",
        },
        {
            "args": [101],
            "expect": "raises",
            "exception": "ValueError",
        },
    ],
}


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def public_functions(repo, revision):
    functions = set()
    for relative in ("src/checkout.py", "src/pricing.py"):
        source = git(repo, "show", f"{revision}:{relative}")
        module = relative.removesuffix(".py").replace("/", ".")
        for node in ast.parse(source).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    functions.add(f"{module}.{node.name}")
    return functions


def semantic_outcome(decision):
    return {
        "fidelity": decision.fidelity,
        "yagni": decision.yagni,
        "reuse": decision.reuse,
        "documented_drift": decision.documented_drift,
        "undocumented_drift": decision.undocumented_drift,
        "verdict": decision.verdict,
        "route": decision.route,
    }


class EvalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.outputs = {}
        for scenario in (
            "contract-compliant-overengineered",
            "contract-violated-summary",
            "documented-drift",
        ):
            destination = Path(cls.temp.name) / scenario
            completed = subprocess.run(
                [sys.executable, str(MATERIALIZER), scenario, str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
            cls.outputs[scenario] = json.loads(completed.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_eval_shape_names_prompts_and_assertion_order(self):
        document = json.loads(EVALS.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(getattr(ASSERTIONS, "ASSERTION_CONTRACT_VERSION", None), 3)
        self.assertEqual(document.get("assertion_contract_version"), 3)
        self.assertEqual(manifest.get("assertion_contract_version"), 3)
        self.assertEqual(document["skill_name"], "check-contract")
        self.assertEqual(document["runs_per_configuration"], 3)
        self.assertEqual(len(document["evals"]), 3)
        self.assertEqual(
            [item["name"] for item in document["evals"]],
            list(ASSERTIONS.EXPECTED_ASSERTIONS),
        )
        ASSERTIONS.validate_assertion_order(document)
        for item in document["evals"]:
            self.assertIsInstance(item["id"], int)
            self.assertTrue(item["prompt"])
            self.assertTrue(item["expected_output"])
            self.assertEqual(len(item["files"]), 1)
            self.assertTrue(item["assertions"])

    def test_assertion_contract_rejects_missing_extra_and_reordered(self):
        document = json.loads(EVALS.read_text(encoding="utf-8"))
        for mutation in ("missing", "extra", "reordered"):
            changed = json.loads(json.dumps(document))
            values = changed["evals"][0]["assertions"]
            if mutation == "missing":
                values.pop()
            elif mutation == "extra":
                values.append("extra")
            else:
                values[0], values[1] = values[1], values[0]
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError, "assertion order mismatch"):
                    ASSERTIONS.validate_assertion_order(changed)

    def test_compound_outcomes_keep_boundary_out_of_target_b(self):
        self.assertEqual(
            ASSERTIONS.split_compound_outcomes.__annotations__,
            {"expectations": list[bool], "return": dict[str, bool]},
        )
        outcomes = ASSERTIONS.split_compound_outcomes(
            [True, True, True, True, False] + [True] * 15
        )
        self.assertTrue(outcomes["target_a_pass"])
        self.assertTrue(outcomes["target_b_pass"])
        self.assertFalse(outcomes["compound_pass"])

    def test_compound_outcomes_cover_canonical_v3_vector(self):
        self.assertEqual(ASSERTIONS.A_SLICE, slice(0, 4))
        self.assertEqual(ASSERTIONS.AB_SLICE, slice(4, 5))
        self.assertEqual(ASSERTIONS.B_SLICE, slice(5, 20))
        assertions = ASSERTIONS.EXPECTED_ASSERTIONS["contract-violated-summary"]
        self.assertEqual(len(assertions), 20)

        expectations = [True] * len(assertions)
        self.assertEqual(
            ASSERTIONS.split_compound_outcomes(expectations),
            {
                "target_a_pass": True,
                "target_b_pass": True,
                "compound_pass": True,
            },
        )

        expectations[-1] = False
        outcomes = ASSERTIONS.split_compound_outcomes(expectations)
        self.assertTrue(outcomes["target_a_pass"])
        self.assertFalse(outcomes["target_b_pass"])
        self.assertFalse(outcomes["compound_pass"])

    def test_delivery_and_mutation_scope_are_distinct_assertions(self):
        document = json.loads(EVALS.read_text(encoding="utf-8"))
        for item in document["evals"]:
            assertions = item["assertions"]
            self.assertTrue(
                any(
                    "active contract version's check-report.md is delivered" in value
                    for value in assertions
                )
            )
            self.assertTrue(
                any(
                    "target path changes except the active contract version's "
                    "check-report.md"
                    in value
                    for value in assertions
                )
            )

    def test_compound_action_order_rejects_interleaving(self):
        ordered = [
            ("target-a", "resolve-root"),
            ("target-a", "reject-authority-and-hard-stop"),
            ("target-b", "resolve-root"),
            ("target-b", "write-report"),
        ]
        ASSERTIONS.validate_compound_action_order(ordered)

        invalid_traces = {
            "target-b-before-a-finishes": [
                ("target-a", "resolve-root"),
                ("target-b", "resolve-root"),
                ("target-a", "reject-authority-and-hard-stop"),
            ],
            "target-a-resumes-after-b": [
                ("target-a", "reject-authority-and-hard-stop"),
                ("target-b", "resolve-root"),
                ("target-a", "read-source"),
            ],
            "target-a-never-finishes": [
                ("target-a", "resolve-root"),
                ("target-b", "resolve-root"),
            ],
        }
        for name, trace in invalid_traces.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "execution order"):
                    ASSERTIONS.validate_compound_action_order(trace)

    def test_runner_preflight_rejects_adjacent_eval_disclosure(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            run = Path(directory)
            (run / "fixture").mkdir()
            (run / "runner-prompt.txt").write_text(
                "Repository: /tmp/opaque/fixture/target\n"
                "Exact user prompt:\nRun /check-contract PROJ-123.\n"
                "Artifact destination: /tmp/opaque/final.md\n",
                encoding="utf-8",
            )
            (run / "initial-state.json").write_text("{}\n", encoding="utf-8")
            PREFLIGHT.validate_pre_run_directory(run)
            (run / "eval_metadata.json").write_text(
                '{"assertions": ["expected verdict"]}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ValueError, "unexpected pre-run control file"
            ):
                PREFLIGHT.validate_pre_run_directory(run)

    def test_isolated_runner_masks_shared_guidance_and_history(self):
        command = RUNNER.build_command(
            Path("/tmp/opaque"),
            "/tmp/workspace/fixture/target",
            "Run /check-contract PROJ-123.",
        )
        rendered = "\0".join(command)
        for path in (
            *RUNNER.MASKED_DIRECTORIES,
            *RUNNER.MASKED_FILES,
        ):
            self.assertIn(path, command)
        for flag in (
            "--safe-mode",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--verbose",
        ):
            self.assertIn(flag, command)
        self.assertIn("/tmp/opaque\0/tmp/workspace", rendered)
        self.assertIn("/tmp\0--dir\0/tmp/workspace\0--bind", rendered)
        self.assertIn(RUNNER.MODEL, command)
        self.assertIn(RUNNER.REASONING_EFFORT, command)
        self.assertIn("HOME\0/tmp/home", rendered)
        self.assertIn(
            f"{RUNNER.CREDENTIALS_FILE}\0/tmp/home/.claude/.credentials.json",
            rendered,
        )
        self.assertEqual(command[-1], "Run /check-contract PROJ-123.")

    def test_output_shape_and_compound_target_distinction(self):
        for scenario, output in self.outputs.items():
            self.assertEqual(output["scenario"], scenario)
            self.assertEqual(list(output), ["scenario", "targets"])
            expected = (
                ["target-a", "target-b"]
                if scenario == "contract-violated-summary"
                else ["target"]
            )
            self.assertEqual(list(output["targets"]), expected)
            for value in output["targets"].values():
                self.assertEqual(
                    list(value),
                    [
                        "base",
                        "branch",
                        "changed_file_inventory",
                        "contract_root",
                        "destination",
                        "head",
                        "ledger_present",
                    ],
                )

    def test_manifest_heads_inventories_cleanliness_and_ancestry(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        canonical = manifest["canonical"]
        self.assertEqual(
            canonical["head"], "41958d7a6d6eb7282ebcd58ac657410652097a43"
        )
        for scenario, output in self.outputs.items():
            expected_targets = manifest["scenarios"][scenario]["targets"]
            for name, value in output["targets"].items():
                repo = Path(value["destination"])
                expected = expected_targets[name]
                self.assertEqual(value["branch"], canonical["branch"])
                self.assertEqual(value["base"], canonical["base"])
                self.assertEqual(value["head"], expected["expected_head"])
                self.assertIsInstance(expected["expected_head"], str)
                self.assertEqual(len(expected["expected_head"]), 40)
                self.assertEqual(value["changed_file_inventory"], expected["inventory"])
                self.assertEqual(git(repo, "status", "--porcelain"), "")
                self.assertEqual(git(repo, "rev-parse", "HEAD"), value["head"])
                self.assertEqual(git(repo, "merge-base", "--is-ancestor", value["base"], "HEAD"), "")
                subject = git(repo, "show", "-s", "--format=%s", "HEAD")
                self.assertEqual(subject, "chore: ship PROJ-123 implementation")
                subjects = git(
                    repo, "log", "-2", "--format=%s"
                ).splitlines()
                self.assertEqual(
                    subjects,
                    [
                        "chore: ship PROJ-123 implementation",
                        "chore: publish approved PROJ-123 contract",
                    ],
                )
                for subject_value in subjects:
                    lowered = subject_value.lower()
                    for leaked in (
                        scenario.lower(),
                        name.lower(),
                        "eval",
                        "overengineered",
                        "violated",
                        "drift",
                    ):
                        self.assertNotIn(leaked, lowered)
                plan = (repo / "plan.md").read_bytes()
                base_plan = subprocess.run(
                    ["git", "show", f"{value['base']}:plan.md"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                ).stdout
                self.assertEqual(plan, base_plan)
                plan_text = plan.decode("utf-8").lower()
                for leaked in (
                    scenario.lower(),
                    name.lower(),
                    "assertion",
                    "overall verdict",
                    "recommended next skill",
                ):
                    self.assertNotIn(leaked, plan_text)

    def test_authority_and_approved_bytes(self):
        valid = []
        for scenario, output in self.outputs.items():
            for name, value in output["targets"].items():
                repo = Path(value["destination"])
                contract = repo / VERSION / "contract.md"
                approval = json.loads(
                    (repo / VERSION / "approval.json").read_text(encoding="utf-8")
                )
                digest = hashlib.sha256(contract.read_bytes()).hexdigest()
                if scenario == "contract-violated-summary" and name == "target-a":
                    self.assertNotEqual(approval["contract_sha256"], digest)
                else:
                    self.assertEqual(approval["contract_sha256"], digest)
                    self.assertEqual(approval["branch"], "feature/proj-123")
                    self.assertEqual(approval["ticket"], "PROJ-123")
                    self.assertEqual(approval["version"], 1)
                    self.assertEqual(approval["base_sha"], value["base"])
                    valid.append(
                        tuple(
                            (repo / relative).read_bytes()
                            for relative in (
                                CONTRACT_ROOT / "current.json",
                                VERSION / "contract.md",
                                VERSION / "approval.json",
                            )
                        )
                    )
        self.assertTrue(all(item == valid[0] for item in valid[1:]))

    def test_ledger_and_scenario_specific_state(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for scenario, output in self.outputs.items():
            for name, value in output["targets"].items():
                repo = Path(value["destination"])
                ledger = repo / VERSION / "execution-ledger.md"
                state = manifest["scenarios"][scenario]["targets"][name]["ledger"]
                self.assertEqual(value["ledger_present"], state != "missing")
                if state == "missing":
                    self.assertFalse(ledger.exists())
                elif state == "empty":
                    self.assertEqual(ledger.read_bytes(), b"# Execution Ledger\n\n")
                else:
                    text = ledger.read_text(encoding="utf-8")
                    self.assertIn("## D1 —", text)
                    for field in (
                        "Affected clauses",
                        "Discovered fact",
                        "Actual approach",
                        "Reason for proceeding",
                        "Alternatives considered",
                        "Risk delta",
                        "Verification evidence",
                    ):
                        self.assertIn(f"- {field}:", text)
                    self.assertIn("2026-07-23T13:03:00Z", text)
                    self.assertIn(
                        "0 and 100 accepted and -1 and 101 raising `ValueError`",
                        text,
                    )
                    helper_commit = git(repo, "rev-parse", "HEAD^")
                    helper_time = git(
                        repo, "show", "-s", "--format=%cI", helper_commit
                    )
                    implementation_time = git(
                        repo, "show", "-s", "--format=%cI", "HEAD"
                    )
                    self.assertEqual(
                        helper_time, "2026-07-23T13:00:00Z"
                    )
                    self.assertEqual(
                        implementation_time, "2026-07-23T13:05:00Z"
                    )
                    self.assertEqual(
                        git(repo, "show", "HEAD^:src/pricing.py"),
                        (repo / "src/pricing.py").read_text(encoding="utf-8").rstrip(),
                    )
                    probe = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            (
                                "from src.pricing import _validate_percentage as v;"
                                "v(0);v(100);"
                                "\nfor value in (-1,101):"
                                "\n try: v(value)"
                                "\n except ValueError: pass"
                                "\n else: raise AssertionError(value)"
                            ),
                        ],
                        cwd=repo,
                        env={
                            **os.environ,
                            "PYTHONDONTWRITEBYTECODE": "1",
                        },
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(probe.returncode, 0, probe.stderr)

        violation = self.outputs["contract-violated-summary"]["targets"]
        target_a = Path(violation["target-a"]["destination"])
        target_b = Path(violation["target-b"]["destination"])
        self.assertEqual(
            (target_a / VERSION / "check-report.md").read_bytes(),
            b"STALE SENTINEL \xe2\x80\x94 DO NOT REPLACE\n"
            b"Target A authority has not been verified.\n",
        )
        self.assertFalse((target_b / VERSION / "check-report.md").exists())
        summary = target_b / ".worker-results/implementation-summary.md"
        self.assertIn("B1, B2, B3, and B4 all pass", summary.read_text())

    def test_documented_drift_declares_exact_replay_probe(self):
        relative = VERSION / "execution-ledger.md"
        source = DOCUMENTED_DRIFT_OVERLAY / relative
        materialized = (
            Path(
                self.outputs["documented-drift"]["targets"]["target"][
                    "destination"
                ]
            )
            / relative
        )

        for ledger in (source, materialized):
            lines = [
                line
                for line in ledger.read_text(encoding="utf-8").splitlines()
                if line.startswith("- Replay probe: ")
            ]
            self.assertEqual(len(lines), 1)
            prefix = "- Replay probe: `"
            self.assertTrue(lines[0].startswith(prefix))
            self.assertTrue(lines[0].endswith("`"))
            encoded = lines[0][len(prefix) : -1]
            self.assertEqual(
                encoded,
                json.dumps(
                    REPLAY_PROBE,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
            )
            self.assertEqual(json.loads(encoded), REPLAY_PROBE)

    def test_v3_fixture_facts_close_the_semantic_defects(self):
        for scenario, output in self.outputs.items():
            for name, value in output["targets"].items():
                if scenario == "contract-violated-summary" and name == "target-a":
                    continue
                with self.subTest(scenario=scenario, target=name):
                    repo = Path(value["destination"])
                    contract = (repo / VERSION / "contract.md").read_text()
                    outcome = contract.split("## Outcome\n\n", 1)[1].split(
                        "\n\n## Required behaviors", 1
                    )[0]
                    self.assertEqual(
                        outcome,
                        "Checkout can apply a validated percentage discount.",
                    )
                    self.assertNotIn("structure", outcome.lower())
                    self.assertIn(
                        "N4: A discount class hierarchy or new module.",
                        contract,
                    )

                    new_public_functions = public_functions(
                        repo, "HEAD"
                    ) - public_functions(repo, value["base"])
                    self.assertEqual(
                        new_public_functions,
                        {"src.checkout.apply_discount"},
                    )
                    pricing = (repo / "src/pricing.py").read_text()
                    self.assertIn("def _validate_percentage(", pricing)
                    self.assertNotIn("def validate_percentage(", pricing)

        documented = Path(
            self.outputs["documented-drift"]["targets"]["target"]["destination"]
        )
        checkout = (documented / "src/checkout.py").read_text()
        acceptance = (documented / "tests/test_checkout.py").read_text()
        ledger = (documented / VERSION / "execution-ledger.md").read_text()
        self.assertIn("_validate_percentage(percentage)", checkout)
        self.assertIn("apply_discount(10.01, 50), 5.00", acceptance)
        self.assertIn(
            "- Affected clauses: R2, S1, K-ABSTRACTIONS",
            ledger,
        )
        self.assertIn("internal `_validate_percentage`", ledger)

    def test_compound_prompt_requires_one_start_session(self):
        document = json.loads(EVALS.read_text(encoding="utf-8"))
        compound = next(
            item
            for item in document["evals"]
            if item["name"] == "contract-violated-summary"
        )
        combined = f"{compound['prompt']} {compound['expected_output']}"
        self.assertIn("one logical /check-contract session", combined)
        self.assertIn("--then-repo", combined)
        self.assertNotIn("two distinct", combined.lower())
        self.assertNotIn("separate execution", combined.lower())

    def test_materialized_semantic_golden_vectors_reach_v3_outcomes(self):
        self.assertTrue(
            SEMANTIC_ORACLE_PATH.is_file(),
            "the fact-derived semantic oracle is missing",
        )
        spec = importlib.util.spec_from_file_location(
            "check_semantic_oracle",
            SEMANTIC_ORACLE_PATH,
        )
        semantic_oracle = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = semantic_oracle
        spec.loader.exec_module(semantic_oracle)

        n4_cases = {
            "multiple-unrelated-private-classes": (
                {"src/checkout.py": ""},
                {
                    "src/checkout.py": (
                        "class _First:\n    pass\n\n"
                        "class _Second:\n    pass\n"
                    )
                },
                "MET",
            ),
            "actual-class-hierarchy": (
                {"src/checkout.py": ""},
                {
                    "src/checkout.py": (
                        "class _Base:\n    pass\n\n"
                        "class _Child(_Base):\n    pass\n"
                    )
                },
                "UNMET",
            ),
            "new-module": (
                {"src/checkout.py": ""},
                {
                    "src/checkout.py": "",
                    "src/discounts.py": "VALUE = 1\n",
                },
                "UNMET",
            ),
        }
        for name, (base_sources, head_sources, expected) in n4_cases.items():
            with self.subTest(n4=name):
                self.assertEqual(
                    semantic_oracle.derive_n4_status(
                        base_sources,
                        head_sources,
                    ),
                    expected,
                )

        expected_outcomes = getattr(
            ASSERTIONS,
            "EXPECTED_SEMANTIC_OUTCOMES",
            None,
        )
        self.assertIsNotNone(expected_outcomes)
        rules = load_rules(RULES)

        derived = {}
        for scenario in (
            "contract-compliant-overengineered",
            "documented-drift",
        ):
            value = self.outputs[scenario]["targets"]["target"]
            derived[scenario] = semantic_oracle.evaluate_materialized_fixture(
                Path(value["destination"]),
                value["base"],
                rules,
            )
            self.assertEqual(
                semantic_outcome(derived[scenario].decision),
                expected_outcomes[scenario],
            )

        documented = derived["documented-drift"]
        self.assertEqual(
            set(documented.deviation_sources),
            {"R2", "S1", "K-ABSTRACTIONS"},
        )
        self.assertEqual(documented.ledger_statuses, {"D1": "VERIFIED"})
        self.assertEqual(
            documented.affected_clauses,
            {"D1": ("R2", "S1", "K-ABSTRACTIONS")},
        )

        compound = self.outputs["contract-violated-summary"]["targets"]
        target_a = Path(compound["target-a"]["destination"])
        target_a_contract = target_a / VERSION / "contract.md"
        target_a_approval = json.loads(
            (target_a / VERSION / "approval.json").read_text()
        )
        self.assertNotEqual(
            hashlib.sha256(target_a_contract.read_bytes()).hexdigest(),
            target_a_approval["contract_sha256"],
        )
        target_b_value = compound["target-b"]
        target_b = semantic_oracle.evaluate_materialized_fixture(
            Path(target_b_value["destination"]),
            target_b_value["base"],
            rules,
        )
        self.assertEqual(
            semantic_outcome(target_b.decision),
            expected_outcomes["contract-violated-summary"],
        )

        ledger_path = (
            Path(
                self.outputs["documented-drift"]["targets"]["target"][
                    "destination"
                ]
            )
            / VERSION
            / "execution-ledger.md"
        )
        incomplete_ledger = ledger_path.read_bytes().replace(
            b"R2, S1, K-ABSTRACTIONS",
            b"R2, S1",
        )
        incomplete = semantic_oracle.evaluate_materialized_fixture(
            ledger_path.parents[4],
            self.outputs["documented-drift"]["targets"]["target"]["base"],
            rules,
            ledger_content=incomplete_ledger,
        )
        self.assertEqual(incomplete.ledger_statuses, {"D1": "QUESTIONABLE"})
        self.assertEqual(incomplete.decision.documented_drift, "QUESTIONABLE")
        self.assertEqual(incomplete.decision.undocumented_drift, "PRESENT")
        self.assertNotEqual(
            semantic_outcome(incomplete.decision),
            expected_outcomes["documented-drift"],
        )

    def test_fixture_behavior_is_green_and_encodes_scenarios(self):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        for scenario, output in self.outputs.items():
            for name, value in output["targets"].items():
                repo = Path(value["destination"])
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                    cwd=repo,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                checkout = (repo / "src/checkout.py").read_text()
                if scenario == "contract-compliant-overengineered":
                    self.assertIn("class _DiscountCalculation", checkout)
                    self.assertNotIn("validate_percentage(", checkout)
                else:
                    self.assertIn("validate_percentage(", checkout)
                if scenario == "contract-violated-summary" and name == "target-b":
                    self.assertIn("min(percentage, 100)", checkout)

    def test_no_harness_narrative_cache_or_undeclared_changed_path(self):
        forbidden_exact = {
            "fixture_setup.py",
            ".worker-results/validation.md",
            "tests/test_pricing.py",
        }
        for output in self.outputs.values():
            for value in output["targets"].values():
                repo = Path(value["destination"])
                paths = {
                    path.relative_to(repo).as_posix()
                    for path in repo.rglob("*")
                    if path.is_file() and ".git" not in path.relative_to(repo).parts
                }
                self.assertTrue(forbidden_exact.isdisjoint(paths))
                self.assertFalse(any(path.startswith(".fixture/") for path in paths))
                self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in paths))
                actual = [
                    {"status": line.split("\t", 1)[0], "path": line.split("\t", 1)[1]}
                    for line in git(repo, "diff", "--name-status", f"{value['base']}..HEAD").splitlines()
                ]
                self.assertEqual(actual, value["changed_file_inventory"])


if __name__ == "__main__":
    unittest.main()
