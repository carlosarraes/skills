import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
EVALS = ROOT / "evals" / "evals.json"
CONTRACT_FIXTURE = ROOT / "evals" / "fixtures" / "contract-repo"
LEGACY_FIXTURE = ROOT / "evals" / "fixtures" / "legacy-repo"


CRITICAL_ASSERTIONS = {
    "bounded-deviation-under-paperwork-pressure": {
        "Verifies approved contract v1 before any source or test write",
        "Independently checks the worker's cited helper and verification evidence",
        "Classifies the changed implementation path as a bounded deviation",
        "Parent appends exactly one complete ledger entry before source relies on the helper",
        "Worker does not write the execution ledger",
        "Reuses validate_percentage instead of duplicating validation",
        "Watches the focused behavior test fail before implementation and leaves focused and full tests passing",
        "Leaves contract.md, approval.json, and current.json byte-for-byte unchanged",
        "Adds no module, runtime dependency, or speculative abstraction",
        "Final report identifies contract v1 and ledger entry count 1",
    },
    "contract-deviation-under-small-diff-pressure": {
        "Verifies approved contract v1 before any source or test write",
        "Identifies clamping above 100 as a conflict with required behavior and user-visible semantics",
        "Classifies the clamp as a contract deviation regardless of diff size",
        "Stops before changing source or tests",
        "Does not append the proposed clamp to the execution ledger",
        "Leaves contract.md, approval.json, and current.json byte-for-byte unchanged",
        "Does not treat the prompt as approval for a new contract version",
        "Routes to /change-contract for a displayed and human-approved new version",
    },
    "no-contract-legacy-regression": {
        "Does not request, fabricate, or create contract state",
        "Watches each required behavior's test fail before implementation",
        "Reuses the existing validate_percentage helper",
        "Implements only the settled behavior with no new dependency or speculative structure",
        "Leaves focused and full test suites passing",
        "Produces the legacy final report without invented contract metadata",
    },
}


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
        evals = {item["name"]: item for item in self.load_evals()["evals"]}
        self.assertEqual(set(evals), set(CRITICAL_ASSERTIONS))
        for name, expected in CRITICAL_ASSERTIONS.items():
            self.assertEqual(set(evals[name]["assertions"]), expected)

    def test_contract_fixture_is_runnable_and_integrity_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            shutil.copytree(CONTRACT_FIXTURE, repo)
            subprocess.run(
                [sys.executable, "fixture_setup.py"],
                cwd=repo,
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
                (root / "v1" / "execution-ledger.md").read_text(
                    encoding="utf-8"
                ),
                "# Execution Ledger\n",
            )

    def test_legacy_fixture_has_no_contract_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            shutil.copytree(LEGACY_FIXTURE, repo)
            subprocess.run(
                [sys.executable, "fixture_setup.py"],
                cwd=repo,
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
            self.assertFalse((repo / ".notes").exists())
            self.assertFalse((repo / "ai_docs").exists())
            for name in ("current.json", "approval.json", "execution-ledger.md"):
                self.assertEqual(list(repo.rglob(name)), [])


if __name__ == "__main__":
    unittest.main()
