import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL_PATH = ROOT / "SKILL.md"
REFERENCE_PATH = ROOT / "references" / "evidence-format.md"

REQUIRED_SKILL_TEXT = [
    "qa-ticket",
    "build-video-evidence.py",
    "snapdoc whoami",
    "--poster",
    "headRefOid",
    "repository visibility",
    "first outward action",
    "version-pinned",
    "backend-only",
    "references/evidence-format.md",
]

REQUIRED_REFERENCE_TEXT = [
    "<!-- qa-pr-evidence -->",
    "<!-- qa-pr-video-artifact:",
    "<!-- qa-pr-report-artifact:",
    "accTitle:",
    "accDescr:",
    "#t=",
    "Video SHA-256",
    "Test-plan SHA-256",
    "Previous runs",
]


def parse_frontmatter(document: str) -> dict[str, str]:
    if not document.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    raw, _body = document[4:].split("\n---\n", 1)
    fields = {}
    current = None
    for line in raw.splitlines():
        if line.startswith((" ", "\t")):
            if current:
                fields[current] += " " + line.strip()
            continue
        key, value = line.split(":", 1)
        current = key.strip()
        fields[current] = value.strip()
    description = fields.get("description", "")
    marker, separator, content = description.partition(" ")
    if marker in {">", ">-", "|", "|-"}:
        fields["description"] = content if separator else ""
    return fields


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_PATH.read_text()
        cls.reference = REFERENCE_PATH.read_text()

    def test_skill_routes_every_required_behavior(self):
        for phrase in REQUIRED_SKILL_TEXT:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.skill)

    def test_reference_owns_the_evidence_shapes(self):
        for phrase in REQUIRED_REFERENCE_TEXT:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.reference)

    def test_description_is_trigger_only_and_compact(self):
        description = parse_frontmatter(self.skill)["description"]
        self.assertTrue(description.startswith("Use when"))
        self.assertLess(len(description), 500)
        for implementation_detail in [
            "localhost",
            "screenshots",
            "sticky",
            "runs the same",
            "checkpoints",
        ]:
            with self.subTest(implementation_detail=implementation_detail):
                self.assertNotIn(implementation_detail, description.lower())

    def test_obsolete_per_run_artifact_rule_is_absent(self):
        obsolete = "new artifact for every QA run"
        self.assertNotIn(obsolete, self.skill)
        self.assertNotIn(obsolete, self.reference)


if __name__ == "__main__":
    unittest.main()
