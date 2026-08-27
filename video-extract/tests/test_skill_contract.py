import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
EXPECTED_FRONTMATTER = {
    "name": "video-extract",
    "description": "Use only when explicitly invoked to extract clean transcripts from YouTube videos.",
    "disable-model-invocation": True,
}
EXPECTED_BODY_SHA256 = "369eca03a58bc120e29434ce0819d2cbeebf05f2b0b1ba402ffed191083ea741"


def split_frontmatter(document):
    if not document.startswith(b"---\n"):
        raise ValueError("missing YAML frontmatter")
    try:
        raw, body = document[4:].split(b"\n---\n", 1)
    except ValueError as error:
        raise ValueError("missing closing YAML frontmatter delimiter") from error
    return raw, body


def parse_frontmatter(document):
    raw, _body = split_frontmatter(document)
    metadata = {}
    for line in raw.split(b"\n"):
        key_bytes, separator, value = line.partition(b":")
        if not separator:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        try:
            key = key_bytes.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("frontmatter keys must be ASCII") from error
        if key not in EXPECTED_FRONTMATTER:
            raise ValueError(f"unexpected frontmatter key: {key!r}")
        if key in metadata:
            raise ValueError(f"duplicate frontmatter key: {key!r}")
        expected = (
            b" true"
            if key == "disable-model-invocation"
            else b" " + EXPECTED_FRONTMATTER[key].encode("utf-8")
        )
        if value != expected:
            raise ValueError(f"invalid exact value for frontmatter key: {key!r}")
        metadata[key] = (
            True
            if key == "disable-model-invocation"
            else value[1:].decode("utf-8")
        )
    if set(metadata) != set(EXPECTED_FRONTMATTER):
        raise ValueError("frontmatter keys are incomplete")
    return metadata


def frontmatter_document(*lines):
    return ("---\n" + "\n".join(lines) + "\n---\nbody").encode("utf-8")


def post_frontmatter_body(document):
    return split_frontmatter(document)[1]


def normalized(text):
    return " ".join(text.split()).lower()


class VideoExtractSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill_bytes = SKILL.read_bytes()
        self.skill = SKILL.read_text(encoding="utf-8")
        self.flat_skill = normalized(self.skill)

    def test_user_invoked_frontmatter_has_exact_boundary(self):
        metadata = parse_frontmatter(self.skill_bytes)
        self.assertEqual(metadata, EXPECTED_FRONTMATTER)
        self.assertIs(metadata["disable-model-invocation"], True)

    def test_frontmatter_parser_rejects_duplicate_extra_and_non_literal_metadata(self):
        duplicate = frontmatter_document(
            "name: video-extract",
            "name: video-extract",
            "description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.",
            "disable-model-invocation: true",
        )
        with self.assertRaises(ValueError):
            parse_frontmatter(duplicate)

        extra = frontmatter_document(
            "name: video-extract",
            "description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.",
            "disable-model-invocation: true",
            "unexpected: value",
        )
        with self.assertRaises(ValueError):
            parse_frontmatter(extra)

        for value in ("yes", "on", "True", "TRUE", '"true"', "true # comment"):
            with self.subTest(value=value):
                malformed_flag = frontmatter_document(
                    "name: video-extract",
                    "description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.",
                    f"disable-model-invocation: {value}",
                )
                with self.assertRaises(ValueError):
                    parse_frontmatter(malformed_flag)

        for description in (
            "Use only when explicitly invoked to extract clean transcripts from YouTube videos. # comment",
            '"Use only when explicitly invoked to extract clean transcripts from YouTube videos."',
        ):
            with self.subTest(description=description):
                malformed_description = frontmatter_document(
                    "name: video-extract",
                    f"description: {description}",
                    "disable-model-invocation: true",
                )
                with self.assertRaises(ValueError):
                    parse_frontmatter(malformed_description)

    def test_skill_body_matches_pinned_pre_task_baseline(self):
        body = post_frontmatter_body(self.skill_bytes)
        self.assertEqual(
            hashlib.sha256(body).hexdigest(),
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
