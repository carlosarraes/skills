import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).parents[1] / "scripts" / "build-video-evidence.py"
)
spec = importlib.util.spec_from_file_location("qa_pr_video_builder", SCRIPT)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


class CaseValidationTests(unittest.TestCase):
    def test_rejects_duplicate_case_ids(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            clip = root / "clip.webm"
            clip.write_bytes(b"video")
            cases = root / "cases.json"
            cases.write_text(
                json.dumps(
                    [
                        {"id": "T1", "title": "First", "file": str(clip)},
                        {"id": "T1", "title": "Second", "file": str(clip)},
                    ]
                )
            )
            with self.assertRaisesRegex(ValueError, "duplicate case ID T1"):
                builder.load_cases(cases)

    def test_rejects_missing_and_empty_clips(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            empty = root / "empty.webm"
            empty.touch()
            for filename, message in [
                ("missing.webm", "not a readable file"),
                ("empty.webm", "is empty"),
            ]:
                with self.subTest(filename=filename):
                    cases = root / "cases.json"
                    cases.write_text(
                        json.dumps(
                            [{"id": "T1", "title": "Case", "file": filename}]
                        )
                    )
                    with self.assertRaisesRegex(ValueError, message):
                        builder.load_cases(cases)

    def test_rejects_invalid_ids_and_empty_titles(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            clip = root / "clip.webm"
            clip.write_bytes(b"video")
            for case_id, title, message in [
                ("case 1", "Title", "invalid case ID"),
                ("T1", "  ", "non-empty title"),
            ]:
                with self.subTest(case_id=case_id, title=title):
                    cases = root / "cases.json"
                    cases.write_text(
                        json.dumps(
                            [{"id": case_id, "title": title, "file": str(clip)}]
                        )
                    )
                    with self.assertRaisesRegex(ValueError, message):
                        builder.load_cases(cases)

    def test_preserves_input_order_and_resolves_relative_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in ("one.webm", "two.webm"):
                (root / name).write_bytes(b"video")
            cases = root / "cases.json"
            cases.write_text(
                json.dumps(
                    [
                        {"id": "T2", "title": "Second", "file": "two.webm"},
                        {"id": "T1", "title": "First", "file": "one.webm"},
                    ]
                )
            )

            loaded = builder.load_cases(cases)

            self.assertEqual([case.case_id for case in loaded], ["T2", "T1"])
            self.assertEqual(loaded[0].file, (root / "two.webm").resolve())


class ChapterMetadataTests(unittest.TestCase):
    def test_builds_contiguous_millisecond_ranges(self):
        clips = [
            builder.CaseClip("T1", "Blocked submit", Path("one.webm")),
            builder.CaseClip("T2", "First error wins", Path("two.webm")),
        ]
        probes = [
            builder.Probe(1250, 640, 360),
            builder.Probe(1750, 640, 360),
        ]

        chapters = builder.build_chapters(clips, probes)

        self.assertEqual(
            [(chapter.start_ms, chapter.end_ms) for chapter in chapters],
            [(0, 1250), (1250, 3000)],
        )

    def test_renders_exact_ffmetadata(self):
        chapters = [
            builder.Chapter("T1", "Blocked submit", 0, 1250),
            builder.Chapter("T2", "First error wins", 1250, 3000),
        ]

        self.assertEqual(
            builder.render_ffmetadata(chapters),
            ";FFMETADATA1\n"
            "[CHAPTER]\n"
            "TIMEBASE=1/1000\n"
            "START=0\n"
            "END=1250\n"
            "title=T1 — Blocked submit\n"
            "[CHAPTER]\n"
            "TIMEBASE=1/1000\n"
            "START=1250\n"
            "END=3000\n"
            "title=T2 — First error wins\n",
        )

    def test_escapes_special_characters_and_flattens_newlines(self):
        chapter = builder.Chapter("T1", "a=b;c#d\ne", 0, 1250)
        metadata = builder.render_ffmetadata([chapter])
        self.assertIn(r"title=T1 — a\=b\;c\#d e", metadata)

    def test_manifest_contains_sha256_and_total_duration(self):
        with tempfile.TemporaryDirectory() as raw:
            video = Path(raw) / "evidence.mp4"
            video.write_bytes(b"abc")
            chapters = [builder.Chapter("T1", "Case", 0, 1250)]

            manifest = builder.make_video_manifest(
                video,
                chapters,
                builder.Probe(1250, 1280, 720),
            )

            self.assertEqual(
                manifest["video_sha256"],
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )
            self.assertEqual(manifest["total_duration_ms"], 1250)
            self.assertEqual(manifest["video_codec"], "h264")


class FinalVideoValidationTests(unittest.TestCase):
    def test_rejects_video_over_ten_minutes(self):
        with tempfile.TemporaryDirectory() as raw:
            video = Path(raw) / "evidence.mp4"
            video.write_bytes(b"video")
            with self.assertRaisesRegex(ValueError, "exceeds 600 seconds"):
                builder.validate_final_video(
                    video,
                    builder.Probe(600_001, 1280, 720),
                    {"codec_name": "h264", "pix_fmt": "yuv420p"},
                )

    def test_rejects_video_over_size_limit(self):
        with tempfile.TemporaryDirectory() as raw:
            video = Path(raw) / "evidence.mp4"
            with video.open("wb") as stream:
                stream.truncate(100_000_001)
            with self.assertRaisesRegex(ValueError, "exceeds 100000000 bytes"):
                builder.validate_final_video(
                    video,
                    builder.Probe(1000, 1280, 720),
                    {"codec_name": "h264", "pix_fmt": "yuv420p"},
                )

    def test_rejects_wrong_codec_or_pixel_format(self):
        with tempfile.TemporaryDirectory() as raw:
            video = Path(raw) / "evidence.mp4"
            video.write_bytes(b"video")
            for stream, message in [
                ({"codec_name": "vp9", "pix_fmt": "yuv420p"}, "H.264"),
                ({"codec_name": "h264", "pix_fmt": "yuv444p"}, "yuv420p"),
            ]:
                with self.subTest(stream=stream):
                    with self.assertRaisesRegex(ValueError, message):
                        builder.validate_final_video(
                            video,
                            builder.Probe(1000, 1280, 720),
                            stream,
                        )


class FfmpegIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise unittest.SkipTest("ffmpeg and ffprobe are required")
        encoders = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if "libvpx-vp9" not in encoders or "libx264" not in encoders:
            raise unittest.SkipTest("libvpx-vp9 and libx264 are required")

    def make_clip(self, path, color, duration):
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=320x180:r=30:d={duration}",
                "-an",
                "-c:v",
                "libvpx-vp9",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_cli_builds_silent_chaptered_h264_bundle(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.make_clip(root / "one.webm", "red", 1.2)
            self.make_clip(root / "two.webm", "blue", 1.7)
            cases = root / "cases.json"
            cases.write_text(
                json.dumps(
                    [
                        {
                            "id": "T1",
                            "title": "Blocked submit",
                            "file": "one.webm",
                        },
                        {
                            "id": "T2",
                            "title": "First error wins",
                            "file": "two.webm",
                        },
                    ]
                )
            )
            output = root / "bundle"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cases",
                    str(cases),
                    "--output-dir",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            manifest_path = Path(completed.stdout.strip())
            self.assertEqual(manifest_path, (output / "chapters.json").resolve())
            self.assertEqual(completed.stderr, "")
            mp4 = output / "evidence.mp4"
            poster = output / "poster.jpg"
            self.assertTrue(mp4.is_file())
            self.assertGreater(poster.stat().st_size, 0)
            manifest = json.loads(manifest_path.read_text())
            probe = json.loads(
                subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_streams",
                        "-show_chapters",
                        "-of",
                        "json",
                        str(mp4),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            video_stream = next(
                stream
                for stream in probe["streams"]
                if stream["codec_type"] == "video"
            )
            self.assertEqual(video_stream["codec_name"], "h264")
            self.assertEqual(video_stream["pix_fmt"], "yuv420p")
            self.assertEqual(
                (video_stream["width"], video_stream["height"]),
                (1280, 720),
            )
            self.assertEqual(len(probe["chapters"]), 2)
            self.assertEqual(
                [chapter["tags"]["title"] for chapter in probe["chapters"]],
                ["T1 — Blocked submit", "T2 — First error wins"],
            )
            self.assertFalse(
                any(stream["codec_type"] == "audio" for stream in probe["streams"])
            )
            self.assertEqual(
                hashlib.sha256(mp4.read_bytes()).hexdigest(),
                manifest["video_sha256"],
            )
            self.assertEqual(
                [chapter["case_id"] for chapter in manifest["chapters"]],
                ["T1", "T2"],
            )

    def test_malformed_clip_preserves_prior_successful_bundle(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bad_clip = root / "bad.webm"
            bad_clip.write_bytes(b"not a webm")
            cases = root / "cases.json"
            cases.write_text(
                json.dumps(
                    [{"id": "T1", "title": "Broken", "file": "bad.webm"}]
                )
            )
            output = root / "bundle"
            output.mkdir()
            originals = {
                "evidence.mp4": b"old video",
                "poster.jpg": b"old poster",
                "chapters.json": b'{"old": true}',
            }
            for name, content in originals.items():
                (output / name).write_bytes(content)

            with self.assertRaises((RuntimeError, subprocess.CalledProcessError)):
                builder.build(cases, output)

            self.assertEqual(
                {name: (output / name).read_bytes() for name in originals},
                originals,
            )

    def test_probe_rejects_malformed_video(self):
        with tempfile.TemporaryDirectory() as raw:
            clip = Path(raw) / "bad.webm"
            clip.write_bytes(b"not a webm")
            with self.assertRaisesRegex(RuntimeError, "ffprobe failed"):
                builder.probe_video(clip)


if __name__ == "__main__":
    unittest.main()
