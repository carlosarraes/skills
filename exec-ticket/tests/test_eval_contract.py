import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
EVALS = ROOT / "evals" / "evals.json"
MATERIALIZER = ROOT / "evals" / "materialize_fixture.py"
FIXTURE_README = ROOT / "evals" / "README.md"
FIXTURE_MANIFEST = ROOT / "evals" / "fixture-manifest.json"
PLAN = (
    ROOT.parent
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-23-exec-ticket-contract-integration.md"
)
ASSERTION_CONTRACT_PATH = ROOT / "evals" / "assertion_contract.py"
ASSERTION_SPEC = importlib.util.spec_from_file_location(
    "exec_ticket_assertion_contract",
    ASSERTION_CONTRACT_PATH,
)
ASSERTION_CONTRACT = importlib.util.module_from_spec(ASSERTION_SPEC)
ASSERTION_SPEC.loader.exec_module(ASSERTION_CONTRACT)
CRITICAL_ASSERTIONS = ASSERTION_CONTRACT.EXPECTED_ASSERTIONS


class EvalContractTests(unittest.TestCase):
    def load_evals(self):
        return json.loads(EVALS.read_text(encoding="utf-8"))

    def test_eval_document_shape_and_unique_names(self):
        document = self.load_evals()
        self.assertEqual(document["skill_name"], "exec-ticket")
        self.assertEqual(document["runs_per_configuration"], 3)
        self.assertEqual(len(document["evals"]), 3)
        names = [item["name"] for item in document["evals"]]
        self.assertEqual(len(names), len(set(names)))
        for item in document["evals"]:
            self.assertIsInstance(item["id"], int)
            self.assertTrue(item["prompt"])
            self.assertTrue(item["expected_output"])
            self.assertEqual(len(item["files"]), 1)
            self.assertTrue(item["assertions"])

    def test_exact_critical_assertions(self):
        document = self.load_evals()
        ASSERTION_CONTRACT.validate_assertion_order(document)
        evals = {item["name"]: item for item in document["evals"]}
        self.assertEqual(set(evals), set(CRITICAL_ASSERTIONS))
        for name, expected in CRITICAL_ASSERTIONS.items():
            self.assertEqual(evals[name]["assertions"], expected)

    def test_reordered_assertions_fail_the_positional_contract(self):
        document = self.load_evals()
        assertions = document["evals"][1]["assertions"]
        assertions[0], assertions[1] = assertions[1], assertions[0]
        with self.assertRaisesRegex(ValueError, "assertion order mismatch"):
            ASSERTION_CONTRACT.validate_assertion_order(document)

    def test_task3_requires_exclusive_clean_canonical_materialization(self):
        readme = FIXTURE_README.read_text(encoding="utf-8")
        manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        plan = PLAN.read_text(encoding="utf-8")
        sources = {
            "README": readme,
            "manifest": manifest["treatment_preparation"],
            "plan": plan,
        }
        for label, text in sources.items():
            with self.subTest(source=label):
                self.assertNotIn(
                    "copy a preserved accepted baseline",
                    text,
                )
                self.assertNotIn("or copy one of the preserved", text)
                for phrase in (
                    "Task 3",
                    "materialize_fixture.py",
                    "exclusively",
                    "expected HEAD",
                    "clean worktree",
                    "before dispatch",
                ):
                    self.assertIn(phrase, text)

    def test_contract_fixture_is_runnable_and_integrity_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "contract-repo",
                    str(repo),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                    cwd=repo,
                    check=False,
                    capture_output=True,
                    text=True,
                ).returncode,
                0,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "feature/proj-123",
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "41958d7a6d6eb7282ebcd58ac657410652097a43",
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
                "",
            )
            root = repo / ".notes" / "feature-proj-123" / "contract"
            current = json.loads(
                (root / "current.json").read_text(encoding="utf-8")
            )
            self.assertEqual(current, {"version": 1})
            approval = json.loads(
                (root / "v1" / "approval.json").read_text(encoding="utf-8")
            )
            digest = hashlib.sha256(
                (root / "v1" / "contract.md").read_bytes()
            ).hexdigest()
            self.assertEqual(approval["contract_sha256"], digest)
            self.assertEqual(approval["branch"], "feature/proj-123")
            self.assertEqual(approval["ticket"], "PROJ-123")
            self.assertEqual(approval["version"], 1)
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "HEAD^"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                approval["base_sha"],
            )
            self.assertIn(
                "def validate_percentage",
                (repo / "src" / "pricing.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (root / "v1" / "execution-ledger.md").read_bytes(),
                b"# Execution Ledger\n\n",
            )

    def test_legacy_fixture_has_no_contract_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "legacy-repo",
                    str(repo),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "feature/proj-123",
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "10bf362f358cc49e193dff07e8b1ee13b452a6b3",
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
                "",
            )
            self.assertFalse((repo / ".notes").exists())
            self.assertFalse((repo / "ai_docs").exists())
            for name in ("current.json", "approval.json", "execution-ledger.md"):
                self.assertEqual(list(repo.rglob(name)), [])


if __name__ == "__main__":
    unittest.main()
