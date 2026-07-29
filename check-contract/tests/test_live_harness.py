import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).resolve().parents[1] / "evals" / "live_harness.py"
MATERIALIZER = ROOT / "check-contract" / "evals" / "materialize_fixture.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class IterationSevenLiveHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = load(HARNESS, "iteration7_live_harness")

    def materialize(self, destination):
        result = subprocess.run(
            [
                sys.executable,
                str(MATERIALIZER),
                "contract-compliant-overengineered",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(json.loads(result.stdout)["targets"]["target"]["destination"])

    def test_exact_unittest_behavior_cannot_dirty_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = self.materialize(Path(temporary) / "fixture")
            before = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

            result = self.harness.run_contained_subject(
                repo,
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-v",
                ],
            )

            after = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(after, before)
            self.assertEqual(list(repo.rglob("*.pyc")), [])
            self.assertEqual(list(repo.rglob("__pycache__")), [])

    def test_subject_command_has_read_only_targets_and_no_broker_storage(self):
        command = self.harness.isolated_subject_command(
            Path("/tmp/run"),
            {"target": Path("/tmp/host-target")},
            Path("/tmp/runtime"),
            ["subject", "--protocol-only"],
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE", command)
        self.assertIn("1", command)
        target_index = command.index("/tmp/host-target")
        self.assertEqual(command[target_index - 1], "--ro-bind")
        self.assertNotIn("trusted-report-staging", " ".join(command))

    def test_trusted_host_publishes_after_subject_read_only_phase(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = self.materialize(Path(temporary) / "fixture")
            report = b"# Contract check report\n\ntrusted host publication\n"
            relative = Path(
                ".notes/feature-proj-123/contract/v1/check-report.md"
            )

            result = self.harness.publish_trusted_report(
                repo, relative, report
            )

            self.assertEqual(result["report_path"], str(repo / relative))
            self.assertEqual(
                result["report_sha256"], hashlib.sha256(report).hexdigest()
            )
            self.assertTrue(result["only_active_report_changed"])
            self.assertEqual((repo / relative).read_bytes(), report)

    def test_runtime_deadline_precedes_outer_watchdog_in_provenance(self):
        self.assertEqual(
            self.harness.terminal_order(
                runtime_code="DEADLINE_EXPIRED", outer_timed_out=True
            ),
            ("runtime:DEADLINE_EXPIRED", "outer-watchdog:360s"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
