"""Bounded one-shot execution for runtime-issued Python replay probes."""

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ARCHIVE_LIMIT = 64 * 1024 * 1024
OUTPUT_LIMIT = 1024 * 1024
PROBE_TIMEOUT_SECONDS = 30.0
_PROBE_PROGRAM = r"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.getcwd())
probe = json.loads(sys.argv[1])
function = getattr(importlib.import_module(probe["module"]), probe["callable"])
for case in probe["cases"]:
    raised = None
    try:
        function(*case["args"])
    except ValueError:
        raised = "ValueError"
    except BaseException:
        raise SystemExit(3)
    if case["expect"] == "returns" and raised is not None:
        raise SystemExit(4)
    if case["expect"] == "raises" and raised != case["exception"]:
        raise SystemExit(5)
""".strip()


@dataclass(frozen=True)
class ProbeObservation:
    probe_id: str
    success: bool
    timed_out: bool
    exit_code: int | None
    reason: str


def _safe_extract(archive: bytes, destination: Path) -> None:
    total = 0
    seen = set()
    try:
        source = tarfile.open(fileobj=io.BytesIO(archive), mode="r:")
    except tarfile.TarError as error:
        raise ValueError("recorded-HEAD probe archive is invalid") from error
    with source:
        for member in source:
            relative = PurePosixPath(member.name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or not relative.parts
                or member.name in seen
            ):
                raise ValueError("recorded-HEAD probe archive is unsafe")
            seen.add(member.name)
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError(
                    "recorded-HEAD probe archive contains a non-file entry"
                )
            total += member.size
            if total > ARCHIVE_LIMIT:
                raise ValueError(
                    "recorded-HEAD probe archive exceeds the byte limit"
                )
            content = source.extractfile(member)
            if content is None:
                raise ValueError(
                    "recorded-HEAD probe archive file is unreadable"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(content.read())


def run_probe(
    *,
    probe_id: str,
    descriptor: dict[str, object],
    repository_root: Path,
    recorded_head: str,
    disposable_root: Path,
    git_runner,
    clock,
    absolute_deadline: float,
) -> ProbeObservation:
    """Run one issued descriptor once from a disposable recorded-HEAD tree."""
    archive_result = git_runner.run(
        ["archive", "--format=tar", recorded_head],
        cwd=repository_root,
        deadline=absolute_deadline,
        output_limit=ARCHIVE_LIMIT,
    )
    if archive_result.timed_out:
        return ProbeObservation(
            probe_id,
            False,
            True,
            None,
            "recorded-HEAD archive timed out",
        )
    if archive_result.truncated:
        return ProbeObservation(
            probe_id,
            False,
            False,
            None,
            "recorded-HEAD archive exceeded the byte limit",
        )
    remaining = min(
        PROBE_TIMEOUT_SECONDS,
        max(0.0, absolute_deadline - clock()),
    )
    if remaining <= 0:
        return ProbeObservation(
            probe_id,
            False,
            True,
            None,
            "audit deadline expired before probe execution",
        )
    Path(disposable_root).mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix="contract-audit-probe-",
            dir=disposable_root,
        ) as temporary:
            tree = Path(temporary)
            _safe_extract(archive_result.stdout, tree)
            descriptor_json = json.dumps(
                descriptor,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            environment = {
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": os.defpath,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHONIOENCODING": "utf-8",
            }
            with tempfile.TemporaryFile() as output:
                try:
                    process = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            "-B",
                            "-c",
                            _PROBE_PROGRAM,
                            descriptor_json,
                        ],
                        cwd=tree,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=output,
                        stderr=output,
                        timeout=remaining,
                        check=False,
                        shell=False,
                    )
                except subprocess.TimeoutExpired:
                    return ProbeObservation(
                        probe_id,
                        False,
                        True,
                        None,
                        "probe execution timed out",
                    )
                output.seek(0, os.SEEK_END)
                if output.tell() > OUTPUT_LIMIT:
                    return ProbeObservation(
                        probe_id,
                        False,
                        False,
                        process.returncode,
                        "probe output exceeded the byte limit",
                    )
            if process.returncode != 0:
                return ProbeObservation(
                    probe_id,
                    False,
                    False,
                    process.returncode,
                    "probe observation did not match the descriptor",
                )
            return ProbeObservation(
                probe_id,
                True,
                False,
                0,
                "probe observation matched the descriptor",
            )
    except (OSError, tarfile.TarError, ValueError) as error:
        return ProbeObservation(
            probe_id,
            False,
            False,
            None,
            f"probe execution failed: {error}",
        )


__all__ = ["ProbeObservation", "run_probe"]
