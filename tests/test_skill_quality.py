import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_quality.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skill_quality", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def init_repo(files):
    directory = tempfile.TemporaryDirectory()
    root = Path(directory.name)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
        cwd=root,
        check=True,
    )
    return directory, root


README = "# Skills\n\n<!-- SKILL-CATALOG:START -->\n| Skill | Description |\n|-------|-------------|\n<!-- SKILL-CATALOG:END -->\n\nTail\n"


class SkillQualityTests(unittest.TestCase):
    def test_first_party_descriptions_fit_the_routing_metadata_budget(self):
        result = load_module().check(ROOT)

        self.assertEqual(result["inventory_count"], 17)
        self.assertEqual(
            {skill["name"] for skill in result["skills"]},
            {
                "atomic-commit", "carraes-reviewer", "check-data", "clean-up",
                "create-verification-skill",
                "exec-ticket", "interrogate", "opening-prs", "pr-sweep", "prep-ticket",
                "maintain-verification-skill",
                "qa-team", "qa-ticket", "simplification-audit", "split-pr",
                "triage-incident", "video-extract",
            },
        )
        self.assertLessEqual(result["description_characters"], 9_320)
        self.assertTrue(
            all(
                skill["description"].startswith(
                    ("Use when", "Use only when explicitly invoked")
                )
                for skill in result["skills"]
            )
        )

    def test_discovers_only_tracked_skill_files(self):
        temp, root = init_repo({
            "one/SKILL.md": "---\nname: one\ndescription: Use when one applies\n---\n# One\n",
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        (root / "ignored" / "SKILL.md").parent.mkdir()
        (root / "ignored" / "SKILL.md").write_text("not tracked", encoding="utf-8")
        self.assertEqual(load_module().discover_skill_paths(root), ["one/SKILL.md"])

    def test_parses_quoted_and_folded_descriptions(self):
        quality = load_module()
        quoted = quality.parse_frontmatter('---\nname: quoted\ndescription: "Use when quoted applies"\n---\nbody')
        folded = quality.parse_frontmatter('---\nname: folded\ndescription: >\n  Use when folded\n  text applies\n---\nbody')
        self.assertEqual(quoted["description"], "Use when quoted applies")
        self.assertEqual(folded["description"], "Use when folded text applies")

    def test_accepts_user_only_description_after_syncing_catalog(self):
        temp, root = init_repo({
            "manual/SKILL.md": (
                "---\nname: manual\n"
                "description: Use only when explicitly invoked to inspect one thing.\n"
                "---\n# Manual\n"
            ),
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        quality = load_module()

        quality.sync_readme(root)

        self.assertEqual(quality.check(root)["errors"], [])

    def test_reports_duplicate_long_and_implementation_heavy_descriptions(self):
        long_description = "Use when " + ("x" * 321) + " then run `git status` with 3 agents and write output to report.md"
        temp, root = init_repo({
            "a/SKILL.md": f"---\nname: same\ndescription: {long_description}\n---\n# A\n",
            "b/SKILL.md": "---\nname: same\ndescription: Use when b applies\n---\n# B\n",
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        result = load_module().check(root)
        messages = "\n".join(result["errors"])
        self.assertIn("duplicate skill name: same", messages)
        self.assertIn("description exceeds 320 characters", messages)
        self.assertIn("implementation leakage", messages)

    def test_reports_broken_local_markdown_references(self):
        temp, root = init_repo({
            "one/SKILL.md": "---\nname: one\ndescription: Use when one applies\n---\n[missing](references/nope.md)\n",
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        result = load_module().check(root)
        self.assertIn("one/SKILL.md: broken local link: references/nope.md", result["errors"])

    def test_check_exit_and_json_schema(self):
        temp, root = init_repo({
            "one/SKILL.md": "---\nname: one\ndescription: Use when one applies\n---\n# One\n",
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "check", "--json"], cwd=root, text=True, capture_output=True
        )
        result = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)  # an empty catalog is intentional drift
        self.assertEqual(result["inventory_count"], 1)
        self.assertIn("description_characters", result)
        self.assertIn("skills", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)

    def test_check_exits_zero_when_the_managed_catalog_is_current(self):
        temp, root = init_repo({
            "one/SKILL.md": "---\nname: one\ndescription: Use when one applies\n---\n# One\n",
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        load_module().sync_readme(root)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "check", "--json"], cwd=root, text=True, capture_output=True
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["errors"], [])

    def test_sync_is_deterministic_and_preserves_text_outside_markers(self):
        before = "prefix\n<!-- SKILL-CATALOG:START -->\nold\n<!-- SKILL-CATALOG:END -->\nsuffix\n"
        temp, root = init_repo({
            "one/SKILL.md": "---\nname: one\ndescription: Use when one applies\n---\n# One\n",
            "two/SKILL.md": "---\nname: two\ndescription: Use when two applies\n---\n# Two\n",
            "README.md": before,
        })
        self.addCleanup(temp.cleanup)
        quality = load_module()
        quality.sync_readme(root)
        first = (root / "README.md").read_text(encoding="utf-8")
        quality.sync_readme(root)
        second = (root / "README.md").read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("prefix\n<!-- SKILL-CATALOG:START -->\n"))
        self.assertTrue(first.endswith("<!-- SKILL-CATALOG:END -->\nsuffix\n"))
        self.assertIn("| `one` | Use when one applies |", first)

    def test_sync_preserves_crlf_and_binary_bytes_outside_the_catalog_block(self):
        before = b"prefix\x00\r\n<!-- SKILL-CATALOG:START -->\r\nold\r\n<!-- SKILL-CATALOG:END -->\r\nsuffix\xff\r\n"
        temp, root = init_repo({
            "one/SKILL.md": "---\nname: one\ndescription: Use when one applies\n---\n# One\n",
            "README.md": README,
        })
        self.addCleanup(temp.cleanup)
        readme = root / "README.md"
        readme.write_bytes(before)
        quality = load_module()
        quality.sync_readme(root)
        after = readme.read_bytes()
        start = b"<!-- SKILL-CATALOG:START -->"
        end = b"<!-- SKILL-CATALOG:END -->"
        self.assertTrue(after.startswith(before[:before.index(start)]))
        self.assertTrue(after.endswith(before[before.index(end) + len(end):]))
        self.assertIn(b"| `one` | Use when one applies |", after)
