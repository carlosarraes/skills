import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
        )

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

    def test_identical_approval_retry_returns_active_version(self):
        module = load_module()
        first = self.approve(module)

        retried = self.approve(module)

        self.assertEqual(retried, first)
        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )
        self.assertFalse((self.root / "v2").exists())

    def test_changed_approval_metadata_activates_new_version(self):
        module = load_module()
        changed_values = {
            "approved_at": "2026-07-23T13:00:00-03:00",
            "approved_by": "Ana",
            "base_sha": "def456",
            "branch": "feature/proj-124",
            "ticket": "PROJ-124",
        }

        for field, value in changed_values.items():
            with self.subTest(field=field):
                self.root = Path(self.temp.name) / field
                self.approve(module)

                result = self.approve(module, **{field: value})

                self.assertEqual(result["version"], 2)
                self.assertEqual(
                    json.loads(
                        (self.root / "current.json").read_text()
                    )["version"],
                    2,
                )

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

    def test_approve_rejects_missing_active_version(self):
        module = load_module()
        self.root.mkdir()
        (self.root / "current.json").write_text(
            json.dumps({"version": 2}),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            module.ContractStateError,
            "missing contract artifact",
        ):
            self.approve(module)

        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            2,
        )
        self.assertFalse((self.root / "v3").exists())
        self.assertEqual(list(self.root.glob(".v3-*")), [])

    def test_approve_rejects_tampered_active_contract(self):
        module = load_module()
        self.approve(module)
        (self.root / "v1" / "contract.md").write_text(
            "# Contract\n\nTampered\n",
            encoding="utf-8",
        )
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")

        with self.assertRaisesRegex(
            module.ContractStateError,
            "hash mismatch",
        ):
            self.approve(
                module,
                approved_at="2026-07-23T13:00:00-03:00",
            )

        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )
        self.assertFalse((self.root / "v2").exists())
        self.assertEqual(list(self.root.glob(".v2-*")), [])

    def test_explicit_version_remains_verifiable_after_new_approval(self):
        module = load_module()
        self.approve(module)
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")
        self.approve(module, approved_at="2026-07-23T13:00:00-03:00")

        result = module.verify(self.root, 1)

        self.assertTrue(result["valid"])
        self.assertEqual(result["version"], 1)

    def test_verify_rejects_non_object_current_json(self):
        module = load_module()
        self.root.mkdir()
        (self.root / "current.json").write_text("[]\n", encoding="utf-8")

        with self.assertRaisesRegex(
            module.ContractStateError,
            "current contract must be a JSON object",
        ):
            module.verify(self.root)

    def test_cli_verify_rejects_non_object_current_json_without_traceback(self):
        self.root.mkdir()
        (self.root / "current.json").write_text("[]\n", encoding="utf-8")

        result = self.run_cli("verify", "--root", str(self.root))

        self.assertEqual(result.returncode, 1)
        self.assertIn("current contract must be a JSON object", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_verify_rejects_invalid_utf8_current_json(self):
        module = load_module()
        self.root.mkdir()
        (self.root / "current.json").write_bytes(b"\xff")

        with self.assertRaisesRegex(
            module.ContractStateError,
            "invalid UTF-8.*current.json",
        ):
            module.verify(self.root)

    def test_cli_verify_rejects_invalid_utf8_current_without_traceback(self):
        self.root.mkdir()
        (self.root / "current.json").write_bytes(b"\xff")

        result = self.run_cli("verify", "--root", str(self.root))

        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, "invalid UTF-8.*current.json")
        self.assertNotIn("Traceback", result.stderr)

    def test_verify_rejects_invalid_current_version_values(self):
        module = load_module()
        self.root.mkdir()

        for value in (True, 0, "1"):
            with self.subTest(value=value):
                (self.root / "current.json").write_text(
                    json.dumps({"version": value}),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    module.ContractStateError,
                    "invalid contract version",
                ):
                    module.verify(self.root)

    def test_verify_rejects_non_object_approval_json(self):
        module = load_module()
        self.approve(module)
        (self.root / "v1" / "approval.json").write_text(
            "[]\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            module.ContractStateError,
            "approval must be a JSON object",
        ):
            module.verify(self.root)

    def test_cli_verify_rejects_non_object_approval_json_without_traceback(self):
        module = load_module()
        self.approve(module)
        (self.root / "v1" / "approval.json").write_text(
            "[]\n",
            encoding="utf-8",
        )

        result = self.run_cli("verify", "--root", str(self.root))

        self.assertEqual(result.returncode, 1)
        self.assertIn("approval must be a JSON object", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_verify_rejects_invalid_utf8_approval_json(self):
        module = load_module()
        self.approve(module)
        approval_path = self.root / "v1" / "approval.json"
        approval_path.write_bytes(b"\xff")

        with self.assertRaisesRegex(
            module.ContractStateError,
            "invalid UTF-8.*approval.json",
        ):
            module.verify(self.root)

    def test_verify_rejects_invalid_required_approval_fields(self):
        module = load_module()
        self.approve(module)
        approval_path = self.root / "v1" / "approval.json"
        original = json.loads(approval_path.read_text(encoding="utf-8"))
        invalid_values = {
            "approved_at": "",
            "approved_by": 123,
            "base_sha": None,
            "branch": [],
            "contract_sha256": "not-a-sha256",
            "ticket": " ",
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                approval = dict(original)
                approval[field] = value
                approval_path.write_text(
                    json.dumps(approval),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    module.ContractStateError,
                    f"invalid approval field: {field}",
                ):
                    module.verify(self.root)

    def test_verify_rejects_approval_version_mismatch(self):
        module = load_module()
        self.approve(module)
        approval_path = self.root / "v1" / "approval.json"
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        approval["version"] = 2
        approval_path.write_text(json.dumps(approval), encoding="utf-8")

        with self.assertRaisesRegex(
            module.ContractStateError,
            "approval version mismatch",
        ):
            module.verify(self.root, 1)

    def test_cli_approve_emits_json_and_stores_approval_metadata(self):
        result = self.run_cli(
            "approve",
            "--root",
            str(self.root),
            "--draft",
            str(self.draft),
            "--ticket",
            "PROJ-123",
            "--branch",
            "feature/proj-123",
            "--base-sha",
            "abc123",
            "--approved-by",
            "Carlos",
            "--approved-at",
            "2026-07-23T12:00:00-03:00",
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        approval = json.loads(
            (self.root / "v1" / "approval.json").read_text(encoding="utf-8")
        )
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["version"], 1)
        self.assertEqual(
            approval,
            {
                "approved_at": "2026-07-23T12:00:00-03:00",
                "approved_by": "Carlos",
                "base_sha": "abc123",
                "branch": "feature/proj-123",
                "contract_sha256": payload["sha256"],
                "ticket": "PROJ-123",
                "version": 1,
            },
        )

    def test_interrupted_publication_cleans_v2_and_allows_retry(self):
        module = load_module()
        self.approve(module)
        original = (self.root / "v1" / "contract.md").read_bytes()
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")
        real_write_json = module._write_json

        def interrupt_current(path, value):
            if value == {"version": 2}:
                raise OSError("interrupted current publication")
            return real_write_json(path, value)

        with mock.patch.object(
            module,
            "_write_json",
            side_effect=interrupt_current,
        ):
            with self.assertRaisesRegex(
                OSError,
                "interrupted current publication",
            ):
                self.approve(
                    module,
                    approved_at="2026-07-23T13:00:00-03:00",
                )

        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )
        self.assertEqual(
            (self.root / "v1" / "contract.md").read_bytes(),
            original,
        )
        self.assertFalse((self.root / "v2").exists())
        self.assertEqual(list(self.root.glob(".v2-*")), [])

        result = self.approve(
            module,
            approved_at="2026-07-23T13:00:00-03:00",
        )
        self.assertEqual(result["version"], 2)

    def test_retry_activates_complete_version_left_before_pointer_swap(self):
        module = load_module()
        self.approve(module)
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")
        self.approve(module, approved_at="2026-07-23T13:00:00-03:00")
        version_two = (self.root / "v2" / "contract.md").read_bytes()
        (self.root / "current.json").write_text(
            json.dumps({"version": 1}),
            encoding="utf-8",
        )

        result = self.approve(
            module,
            approved_at="2026-07-23T13:00:00-03:00",
        )

        self.assertEqual(result["version"], 2)
        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            2,
        )
        self.assertEqual(
            (self.root / "v2" / "contract.md").read_bytes(),
            version_two,
        )

    def test_retry_does_not_activate_mismatched_complete_version(self):
        module = load_module()
        self.approve(module)
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")
        self.approve(module, approved_at="2026-07-23T13:00:00-03:00")
        (self.root / "current.json").write_text(
            json.dumps({"version": 1}),
            encoding="utf-8",
        )
        self.draft.write_text("# Contract\n\nBehavior C\n", encoding="utf-8")

        with self.assertRaisesRegex(
            module.ContractStateError,
            "contract version already exists",
        ):
            self.approve(
                module,
                approved_at="2026-07-23T14:00:00-03:00",
            )

        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )

    def test_interruption_after_pointer_swap_preserves_active_version(self):
        module = load_module()
        real_write_json_atomic = module._write_json_atomic

        def interrupt_after_swap(path, value):
            real_write_json_atomic(path, value)
            if value == {"version": 1}:
                raise OSError("interrupted after current publication")

        with mock.patch.object(
            module,
            "_write_json_atomic",
            side_effect=interrupt_after_swap,
        ):
            with self.assertRaisesRegex(
                OSError,
                "interrupted after current publication",
            ):
                self.approve(module)

        result = self.approve(module)

        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )
        self.assertEqual(result["version"], 1)
        self.assertTrue(module.verify(self.root)["valid"])
        self.assertEqual(module.verify(self.root)["version"], 1)
        self.assertFalse((self.root / "v2").exists())

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
