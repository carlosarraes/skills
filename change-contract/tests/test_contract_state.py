import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "contract_state.py"


def load_module():
    spec = importlib.util.spec_from_file_location("contract_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ContractStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "contract"
        self.draft = Path(self.temp.name) / "draft.md"
        self.draft.write_text("# Contract\n\nBehavior A\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def approve(self, module, **overrides):
        values = {
            "root": self.root,
            "draft": self.draft,
            "ticket": "PROJ-123",
            "branch": "feature/proj-123",
            "base_sha": "abc123",
            "approved_by": "Carlos",
            "approved_at": "2026-07-23T12:00:00-03:00",
        }
        values.update(overrides)
        return module.approve(**values)

    def test_approve_creates_verifiable_v1(self):
        module = load_module()

        result = self.approve(module)

        self.assertEqual(result["version"], 1)
        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )
        self.assertEqual(
            (self.root / "v1" / "contract.md").read_text(),
            self.draft.read_text(),
        )
        self.assertEqual(
            (self.root / "v1" / "execution-ledger.md").read_text(),
            "# Execution Ledger\n\n",
        )
        self.assertTrue(module.verify(self.root)["valid"])

    def test_second_approval_preserves_v1_and_activates_v2(self):
        module = load_module()
        first = self.approve(module)
        original = (self.root / "v1" / "contract.md").read_text()
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")

        second = self.approve(
            module,
            approved_at="2026-07-23T13:00:00-03:00",
        )

        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        self.assertEqual(
            (self.root / "v1" / "contract.md").read_text(),
            original,
        )
        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            2,
        )

    def test_verify_rejects_modified_approved_contract(self):
        module = load_module()
        self.approve(module)
        (self.root / "v1" / "contract.md").write_text(
            "# Contract\n\nTampered\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(module.ContractStateError, "hash mismatch"):
            module.verify(self.root)

    def test_cli_verify_emits_json_and_nonzero_on_tamper(self):
        module = load_module()
        self.approve(module)
        good = subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "--root", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(good.returncode, 0)
        self.assertTrue(json.loads(good.stdout)["valid"])

        (self.root / "v1" / "contract.md").write_text("tampered\n")
        bad = subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "--root", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(bad.returncode, 1)
        self.assertIn("hash mismatch", bad.stderr)


if __name__ == "__main__":
    unittest.main()
