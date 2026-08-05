import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "evals" / "run.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("skill_evals", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_repo():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "one" / "evals").mkdir(parents=True)
    (root / "one" / "SKILL.md").write_text(
        "---\nname: one\ndescription: Use when one applies\n---\n# One\n", encoding="utf-8"
    )
    (root / "one" / "evals" / "evals.json").write_text('[{"id": "b1", "prompt": "do one"}]', encoding="utf-8")
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "fixture"], cwd=root, check=True)
    return temp, root


class EvalRunnerTests(unittest.TestCase):
    def test_behavior_cases_override_still_requires_skill_at_ref(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        cases = root / "behavior-cases.json"
        cases.write_text('[{"id": "override-case", "prompt": "do override"}]', encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "behavior",
                "--skill",
                "missing",
                "--ref",
                "HEAD",
                "--runs",
                "1",
                "--cases",
                str(cases),
                "--dry-run",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("missing/SKILL.md", completed.stderr)

    def test_behavior_cases_override_does_not_require_ref_backed_evals(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        subprocess.run(["git", "rm", "-q", "one/evals/evals.json"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "remove evals"],
            cwd=root,
            check=True,
        )
        cases = root / "behavior-cases.json"
        cases.write_text('{"evals": [{"id": "override-case", "prompt": "do override"}]}', encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "behavior",
                "--skill",
                "one",
                "--ref",
                "HEAD",
                "--runs",
                "1",
                "--cases",
                str(cases),
                "--dry-run",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["results"][0]["case_id"], "override-case")

    def test_behavior_rejects_an_explicit_empty_cases_path(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        completed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "behavior",
                "--skill",
                "one",
                "--ref",
                "HEAD",
                "--runs",
                "1",
                "--cases",
                "",
                "--dry-run",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_behavior_accepts_the_existing_object_evals_shape(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        path = root / "one" / "evals" / "evals.json"
        path.write_text('{"evals": [{"id": "object-case", "prompt": "do one"}]}', encoding="utf-8")
        subprocess.run(["git", "add", "one/evals/evals.json"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "object evals"], cwd=root, check=True)
        result = load_runner().run_behavior(root, "one", "HEAD", 1, None, True, root / "out")
        self.assertEqual(result["results"][0]["case_id"], "object-case")

    def test_routing_dry_run_loads_catalog_from_ref_and_builds_fresh_commands(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        (root / "one" / "SKILL.md").write_text(
            "---\nname: one\ndescription: Use when uncommitted wording applies\n---\n# One\n", encoding="utf-8"
        )
        cases = root / "cases.json"
        cases.write_text('[{"id":"r1","prompt":"do one","expected":"one"}]', encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "routing", "--ref", "HEAD", "--runs", "2", "--cases", str(cases), "--dry-run"],
            cwd=root, text=True, capture_output=True, check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["catalog"], [{"name": "one", "description": "Use when one applies"}])
        self.assertEqual(len(result["results"]), 2)
        command = result["results"][0]["command"]
        self.assertEqual(command[:4], ["codex", "exec", "--ephemeral", "--ignore-user-config"])
        self.assertEqual(command[4:6], ["--sandbox", "read-only"])
        self.assertIn("one: Use when one applies", command[-1])
        self.assertNotIn("claude", " ".join(command).lower())

    def test_behavior_dry_run_reads_evals_at_ref_and_materializes_temporary_tree(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        result = load_runner().run_behavior(root, "one", "HEAD", 1, None, True, root / "out")
        record = result["results"][0]
        self.assertEqual(record["case_id"], "b1")
        self.assertNotEqual(Path(record["worktree"]), root)
        self.assertFalse(Path(record["worktree"]).exists())
        self.assertIn("status", record)
        self.assertIn("diff", record)

    def test_real_behavior_uses_fake_codex_per_sample_and_keeps_live_tree_clean(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        fake_temp = tempfile.TemporaryDirectory()
        self.addCleanup(fake_temp.cleanup)
        fake_bin = Path(fake_temp.name) / "bin"
        fake_bin.mkdir()
        fake = fake_bin / "codex"
        fake.write_text("#!/bin/sh\nprintf fake-response\n", encoding="utf-8")
        fake.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        os.environ["PATH"] = f"{fake_bin}:{old_path}"
        result = load_runner().run_behavior(root, "one", "HEAD", 2, None, False, Path(fake_temp.name) / "out")
        self.assertEqual([r["response"] for r in result["results"]], ["fake-response", "fake-response"])
        self.assertEqual(subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True).stdout, "")

    def test_behavior_passes_absolute_snapshot_skill_authority_to_codex(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        fake_temp = tempfile.TemporaryDirectory()
        self.addCleanup(fake_temp.cleanup)
        fake_bin = Path(fake_temp.name) / "bin"
        fake_bin.mkdir()
        fake = fake_bin / "codex"
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
        fake.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        os.environ["PATH"] = f"{fake_bin}:{old_path}"
        result = load_runner().run_behavior(root, "one", "HEAD", 1, None, False, Path(fake_temp.name) / "out")
        record = result["results"][0]
        snapshot_skill = str(Path(record["worktree"]) / "one" / "SKILL.md")
        self.assertIn(snapshot_skill, record["response"])
        self.assertNotIn(str(root / "one" / "SKILL.md"), record["response"])
        self.assertIn("ignore installed or catalog copies", record["response"].lower())
        self.assertIn("resolve direct references relative to", record["response"].lower())

    def test_behavior_materializes_an_isolated_git_repository_and_captures_edits(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        fake_temp = tempfile.TemporaryDirectory()
        self.addCleanup(fake_temp.cleanup)
        fake_bin = Path(fake_temp.name) / "bin"
        fake_bin.mkdir()
        fake = fake_bin / "codex"
        fake.write_text(
            "#!/bin/sh\ngit rev-parse --is-inside-work-tree\nprintf changed > one/SKILL.md\n", encoding="utf-8"
        )
        fake.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        os.environ["PATH"] = f"{fake_bin}:{old_path}"
        result = load_runner().run_behavior(root, "one", "HEAD", 1, None, False, Path(fake_temp.name) / "out")
        record = result["results"][0]
        self.assertEqual(record["response"], "true")
        self.assertIn("one/SKILL.md", record["status"])
        self.assertIn("-name: one", record["diff"])
        self.assertEqual(subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True).stdout, "")

    def test_behavior_prompt_requires_reading_the_selected_skill_before_acting(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        record = load_runner().run_behavior(root, "one", "HEAD", 1, None, True, root / "out")["results"][0]
        self.assertEqual(record["command"][4:6], ["--sandbox", "workspace-write"])
        self.assertIn("one/SKILL.md", record["command"][-1])
        self.assertIn("read and follow", record["command"][-1].lower())

    def test_behavior_prompt_exempts_only_the_required_snapshot_read_from_case_prohibitions(self):
        prompt = load_runner().behavior_prompt("/tmp/snapshot/one/SKILL.md", "SIMULATION ONLY: no tools or file reads")
        normalized = " ".join(prompt.lower().split())
        self.assertIn("mandatory harness setup", normalized)
        self.assertIn("perform this one skill-file read first", normalized)
        self.assertIn("exempt from any no-tool, no-file-read, or no-command wording", normalized)
        self.assertIn("all evaluation-request constraints apply immediately after", normalized)
        self.assertIn("does not permit reading references", normalized)

    def test_cli_rejects_non_positive_runs(self):
        temp, root = fixture_repo()
        self.addCleanup(temp.cleanup)
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "routing", "--ref", "HEAD", "--runs", "0", "--dry-run"],
            cwd=root, text=True, capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("positive integer", completed.stderr)
