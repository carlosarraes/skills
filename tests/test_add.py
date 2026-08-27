import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AddTests(unittest.TestCase):
    def test_all_prunes_stale_repo_links_and_preserves_foreign_entries(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repository = Path(temp.name) / "repository"
        repository.mkdir()
        shutil.copy2(ROOT / "add", repository / "add")
        (repository / "kept" / "SKILL.md").parent.mkdir()
        (repository / "kept" / "SKILL.md").write_text(
            "---\nname: kept\ndescription: Use when kept applies\n---\n# Kept\n",
            encoding="utf-8",
        )

        home = Path(temp.name) / "home"
        foreign_target = Path(temp.name) / "foreign-target"
        for target_root in (home / ".claude" / "skills", home / ".agents" / "skills"):
            target_root.mkdir(parents=True)
            (target_root / "removed").symlink_to(repository / "removed")
            (target_root / "foreign").symlink_to(foreign_target)
            (target_root / "regular").mkdir()

        environment = os.environ.copy()
        environment["HOME"] = str(home)
        completed = subprocess.run(
            ["bash", str(repository / "add"), "all"],
            cwd=repository,
            env=environment,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for target_root in (home / ".claude" / "skills", home / ".agents" / "skills"):
            self.assertTrue((target_root / "kept").is_symlink())
            self.assertFalse((target_root / "removed").exists())
            self.assertTrue((target_root / "foreign").is_symlink())
            self.assertTrue((target_root / "regular").is_dir())


if __name__ == "__main__":
    unittest.main()
