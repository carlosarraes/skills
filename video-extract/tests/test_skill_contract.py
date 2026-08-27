import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"


def normalized(text):
    return " ".join(text.split()).lower()


class VideoExtractSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.flat_skill = normalized(self.skill)

    def test_user_invoked_frontmatter_has_exact_boundary(self):
        frontmatter = self.skill.split("---", 2)[1]
        self.assertIn("name: video-extract", frontmatter)
        self.assertIn(
            "description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.",
            frontmatter,
        )
        self.assertIn("disable-model-invocation: true", frontmatter)

    def test_caption_first_and_public_video_boundaries_remain(self):
        for phrase in (
            "Captions-first, always.",
            "Only touch the audio-transcription fallback when a video genuinely has no captions.",
            "Public videos only.",
            "don't attempt age-gated/private/members-only videos that need auth.",
        ):
            self.assertIn(normalized(phrase), self.flat_skill)


if __name__ == "__main__":
    unittest.main()
