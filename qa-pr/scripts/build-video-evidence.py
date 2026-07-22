#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


MAX_DURATION_MS = 600_000
MAX_SIZE_BYTES = 100_000_000
MAX_WIDTH = 1280
MAX_HEIGHT = 720
CASE_ID = re.compile(r"^[A-Z][A-Z0-9_-]*$")


@dataclass(frozen=True)
class CaseClip:
    case_id: str
    title: str
    file: Path


@dataclass(frozen=True)
class Probe:
    duration_ms: int
    width: int
    height: int


@dataclass(frozen=True)
class Chapter:
    case_id: str
    title: str
    start_ms: int
    end_ms: int


def load_cases(path: Path) -> list[CaseClip]:
    path = path.resolve()
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read cases JSON: {error}") from error
    if not isinstance(document, list) or not document:
        raise ValueError("cases JSON must be a non-empty array")

    clips = []
    seen = set()
    for index, item in enumerate(document):
        if not isinstance(item, dict):
            raise ValueError(f"case at index {index} must be an object")
        case_id = item.get("id")
        title = item.get("title")
        filename = item.get("file")
        if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
            raise ValueError(f"invalid case ID {case_id!r}")
        if case_id in seen:
            raise ValueError(f"duplicate case ID {case_id}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"case {case_id} requires a non-empty title")
        if not isinstance(filename, str) or not filename:
            raise ValueError(f"case {case_id} requires a file path")

        clip = Path(filename).expanduser()
        if not clip.is_absolute():
            clip = path.parent / clip
        clip = clip.resolve()
        if not clip.is_file() or not os.access(clip, os.R_OK):
            raise ValueError(f"case {case_id} clip is not a readable file: {clip}")
        if clip.stat().st_size == 0:
            raise ValueError(f"case {case_id} clip is empty: {clip}")

        clips.append(CaseClip(case_id, title.strip(), clip))
        seen.add(case_id)
    return clips


def _require_tools() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]
    if missing:
        raise RuntimeError(f"required executable not found: {', '.join(missing)}")


def _run(command: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or "no diagnostic"
        raise RuntimeError(f"command failed ({command[0]}): {detail}") from error


def _probe_document(path: Path, include_chapters: bool = False) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
    ]
    if include_chapters:
        command.append("-show_chapters")
    command.extend(["-of", "json", str(path)])
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise RuntimeError(f"ffprobe failed for {path}: {detail.strip()}") from error


def _probe_from_document(document: dict, path: Path) -> Probe:
    video = next(
        (
            stream
            for stream in document.get("streams", [])
            if stream.get("codec_type") == "video"
        ),
        None,
    )
    if video is None:
        raise RuntimeError(f"ffprobe found no video stream in {path}")
    raw_duration = document.get("format", {}).get("duration") or video.get(
        "duration"
    )
    try:
        duration_ms = int(round(float(raw_duration) * 1000))
        width = int(video["width"])
        height = int(video["height"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"ffprobe returned incomplete video data for {path}") from error
    if duration_ms <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"ffprobe returned invalid video data for {path}")
    return Probe(duration_ms, width, height)


def probe_video(path: Path) -> Probe:
    path = path.resolve()
    return _probe_from_document(_probe_document(path), path)


def build_chapters(
    cases: list[CaseClip], probes: list[Probe]
) -> list[Chapter]:
    if len(cases) != len(probes):
        raise ValueError("cases and probes must have the same length")
    chapters = []
    cursor = 0
    for case, probe in zip(cases, probes):
        if probe.duration_ms <= 0:
            raise ValueError(f"case {case.case_id} has no positive duration")
        end = cursor + probe.duration_ms
        chapters.append(
            Chapter(case.case_id, case.title, cursor, end)
        )
        cursor = end
    return chapters


def _escape_ffmetadata(value: str) -> str:
    flattened = " ".join(value.splitlines())
    return (
        flattened.replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace(";", "\\;")
        .replace("#", "\\#")
    )


def render_ffmetadata(chapters: list[Chapter]) -> str:
    lines = [";FFMETADATA1"]
    for chapter in chapters:
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={chapter.start_ms}",
                f"END={chapter.end_ms}",
                "title="
                + _escape_ffmetadata(f"{chapter.case_id} — {chapter.title}"),
            ]
        )
    return "\n".join(lines) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_video_manifest(
    video: Path, chapters: list[Chapter], probe: Probe
) -> dict:
    return {
        "chapters": [
            {
                "case_id": chapter.case_id,
                "title": chapter.title,
                "start_ms": chapter.start_ms,
                "end_ms": chapter.end_ms,
                "duration_ms": chapter.end_ms - chapter.start_ms,
            }
            for chapter in chapters
        ],
        "video_sha256": sha256_file(video),
        "total_duration_ms": probe.duration_ms,
        "width": probe.width,
        "height": probe.height,
        "video_codec": "h264",
        "size_bytes": video.stat().st_size,
    }


def validate_final_video(video: Path, probe: Probe, video_stream: dict) -> None:
    if probe.duration_ms > MAX_DURATION_MS:
        raise ValueError(
            f"video duration {probe.duration_ms}ms exceeds 600 seconds"
        )
    size = video.stat().st_size
    if size > MAX_SIZE_BYTES:
        raise ValueError(f"video size {size} exceeds 100000000 bytes")
    if probe.width > MAX_WIDTH or probe.height > MAX_HEIGHT:
        raise ValueError(
            f"video dimensions {probe.width}x{probe.height} exceed 1280x720"
        )
    if video_stream.get("codec_name") != "h264":
        raise ValueError("video codec must be H.264")
    if video_stream.get("pix_fmt") != "yuv420p":
        raise ValueError("video pixel format must be yuv420p")
    rate = video_stream.get("r_frame_rate")
    if rate:
        try:
            fps = float(Fraction(rate))
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError(f"invalid video frame rate {rate}") from error
        if not math.isclose(fps, 30.0, abs_tol=0.01):
            raise ValueError(f"video frame rate must be 30fps, got {fps:g}")


def _normalize_clip(source: Path, target: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            (
                "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30"
            ),
            "-map_metadata",
            "-1",
            "-metadata",
            "creation_time=1970-01-01T00:00:00Z",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )


def _concat_line(path: Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'\n"


def _publish_atomically(staged: dict[Path, Path]) -> None:
    backup_root = Path(tempfile.mkdtemp(prefix=".qa-pr-backup-", dir=next(iter(staged.values())).parent))
    backups = {}
    published = []
    try:
        for public in staged.values():
            if public.exists():
                backup = backup_root / public.name
                shutil.copy2(public, backup)
                backups[public] = backup
        for temporary, public in staged.items():
            os.replace(temporary, public)
            published.append(public)
    except Exception:
        for public in published:
            if public in backups:
                os.replace(backups[public], public)
            else:
                public.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)


def build(cases_path: Path, output_dir: Path) -> Path:
    _require_tools()
    cases = load_cases(cases_path)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".qa-pr-video-", dir=output_dir
    ) as raw:
        scratch = Path(raw)
        normalized = []
        probes = []
        for index, case in enumerate(cases, start=1):
            target = scratch / f"{index:03d}-{case.case_id}.mp4"
            try:
                _normalize_clip(case.file, target)
            except RuntimeError as error:
                raise RuntimeError(
                    f"case {case.case_id} clip {case.file}: {error}"
                ) from error
            normalized.append(target)
            probes.append(probe_video(target))

        chapters = build_chapters(cases, probes)
        if chapters[-1].end_ms > MAX_DURATION_MS:
            raise ValueError(
                f"video duration {chapters[-1].end_ms}ms exceeds 600 seconds"
            )

        concat_file = scratch / "concat.txt"
        concat_file.write_text("".join(_concat_line(path) for path in normalized))
        joined = scratch / "joined.mp4"
        _run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(joined),
            ]
        )

        metadata = scratch / "chapters.ffmetadata"
        metadata.write_text(render_ffmetadata(chapters))
        video = scratch / "evidence.tmp.mp4"
        _run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(joined),
                "-i",
                str(metadata),
                "-map",
                "0",
                "-map_metadata",
                "1",
                "-map_chapters",
                "1",
                "-metadata",
                "creation_time=1970-01-01T00:00:00Z",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(video),
            ]
        )

        final_document = _probe_document(video, include_chapters=True)
        final_probe = _probe_from_document(final_document, video)
        video_stream = next(
            stream
            for stream in final_document["streams"]
            if stream.get("codec_type") == "video"
        )
        validate_final_video(video, final_probe, video_stream)
        if any(
            stream.get("codec_type") == "audio"
            for stream in final_document.get("streams", [])
        ):
            raise ValueError("video must be silent")
        actual_chapters = final_document.get("chapters", [])
        expected_titles = [
            f"{chapter.case_id} — {chapter.title}" for chapter in chapters
        ]
        actual_titles = [
            chapter.get("tags", {}).get("title") for chapter in actual_chapters
        ]
        if actual_titles != expected_titles:
            raise ValueError("final video chapters do not match acceptance cases")

        poster_ms = min(1000, final_probe.duration_ms // 2)
        poster = scratch / "poster.tmp.jpg"
        _run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{poster_ms / 1000:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(poster),
            ]
        )

        manifest = make_video_manifest(video, chapters, final_probe)
        manifest_file = scratch / "chapters.tmp.json"
        manifest_file.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        )
        public_video = output_dir / "evidence.mp4"
        public_poster = output_dir / "poster.jpg"
        public_manifest = output_dir / "chapters.json"
        _publish_atomically(
            {
                video: public_video,
                poster: public_poster,
                manifest_file: public_manifest,
            }
        )
    return public_manifest.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a silent chaptered MP4 QA evidence bundle."
    )
    parser.add_argument(
        "--cases",
        required=True,
        type=Path,
        help="JSON array of ordered acceptance-case clips",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="directory for evidence.mp4, poster.jpg, and chapters.json",
    )
    args = parser.parse_args()
    print(build(args.cases, args.output_dir))


if __name__ == "__main__":
    main()
