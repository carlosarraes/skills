import hashlib
import unittest
from pathlib import Path

import yaml
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EXPECTED_FRONTMATTER = {
    "name": "video-extract",
    "description": "Use only when explicitly invoked to extract clean transcripts from YouTube videos.",
    "disable-model-invocation": True,
}
EXPECTED_BODY_SHA256 = "369eca03a58bc120e29434ce0819d2cbeebf05f2b0b1ba402ffed191083ea741"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key ({key!r})",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    construct_unique_mapping,
)


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    raw, _body = text[4:].split("\n---\n", 1)
    metadata = yaml.load(raw, Loader=UniqueKeyLoader)
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a mapping")
    return metadata


def post_frontmatter_body(text):
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    return text[4:].split("\n---\n", 1)[1]


def normalized(text):
    return " ".join(text.split()).lower()


class VideoExtractSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.flat_skill = normalized(self.skill)

    def test_user_invoked_frontmatter_has_exact_boundary(self):
        metadata = parse_frontmatter(self.skill)
        self.assertEqual(metadata, EXPECTED_FRONTMATTER)
        self.assertIs(metadata["disable-model-invocation"], True)

    def test_frontmatter_parser_rejects_duplicate_keys_and_string_flags(self):
        duplicate = (
            "---\n"
            "name: video-extract\n"
            "name: duplicate\n"
            "description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.\n"
            "disable-model-invocation: true\n"
            "---\nbody"
        )
        with self.assertRaises(ConstructorError):
            parse_frontmatter(duplicate)

        quoted_flag = (
            "---\n"
            "name: video-extract\n"
            "description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.\n"
            'disable-model-invocation: "true"\n'
            "---\nbody"
        )
        parsed = parse_frontmatter(quoted_flag)
        self.assertIsInstance(parsed["disable-model-invocation"], str)
        self.assertNotEqual(parsed, EXPECTED_FRONTMATTER)

    def test_skill_body_matches_pinned_pre_task_baseline(self):
        body = post_frontmatter_body(self.skill)
        self.assertEqual(
            hashlib.sha256(body.encode("utf-8")).hexdigest(),
            EXPECTED_BODY_SHA256,
        )

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
