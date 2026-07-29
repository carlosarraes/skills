#!/usr/bin/env python3
"""Native-only helpers for the future iteration-7 harness.

The subject sees read-only target mounts. Request issuance and final report
publication stay on the trusted host side; this module deliberately does not
claim that a shared subject/runtime namespace can hide reads or protect a
session directory from the subject.
"""

import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "check-contract" / "scripts"
OUTER_WATCHDOG_SECONDS = 360


def isolated_subject_command(
    run_root: Path,
    targets: dict[str, Path],
    runtime_snapshot: Path,
    argv: list[str],
) -> list[str]:
    """Build the subject boundary; trusted broker storage is never mounted."""
    command = [
        "bwrap",
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/tmp/workspace",
        "--bind",
        str(run_root),
        "/tmp/workspace",
        "--dir",
        "/tmp/check-contract-runtime",
        "--ro-bind",
        str(runtime_snapshot),
        "/tmp/check-contract-runtime",
    ]
    for name, target in sorted(targets.items()):
        command.extend(
            [
                "--ro-bind",
                str(target),
                f"/tmp/workspace/fixture/{name}",
            ]
        )
    command.extend(
        [
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--chdir",
            "/tmp/workspace/fixture/" + next(iter(sorted(targets))),
            *argv,
        ]
    )
    return command


@contextmanager
def _read_only_tree(root: Path):
    original = {}
    paths = [root, *root.rglob("*")]
    try:
        for path in paths:
            try:
                mode = stat.S_IMODE(path.lstat().st_mode)
            except FileNotFoundError:
                continue
            original[path] = mode
            if not path.is_symlink():
                path.chmod(mode & ~0o222)
        yield
    finally:
        for path, mode in reversed(tuple(original.items())):
            try:
                if not path.is_symlink():
                    path.chmod(mode)
            except FileNotFoundError:
                pass


def run_contained_subject(repo: Path, argv: list[str]):
    """Run a deterministic native self-test under the subject write policy."""
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    with _read_only_tree(Path(repo)):
        return subprocess.run(
            argv,
            cwd=repo,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )


def publish_trusted_report(
    repository_root: Path,
    report_relative: Path,
    report: bytes,
):
    """Publish on the host after the subject phase and attest the exact delta."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        from audit_report import (
            capture_target_state,
            mutation_attestation,
            publish_atomic,
        )
    finally:
        sys.path.pop(0)
    repository_root = Path(repository_root)
    report_relative = Path(report_relative)
    before = capture_target_state(repository_root)
    report_path = repository_root / report_relative
    report_sha256 = publish_atomic(report_path, report)
    after = capture_target_state(repository_root)
    attestation = mutation_attestation(
        before, after, report_relative.as_posix()
    )
    return {
        "report_path": str(report_path),
        "report_sha256": report_sha256,
        **attestation,
    }


def terminal_order(*, runtime_code, outer_timed_out):
    values = []
    if runtime_code is not None:
        values.append(f"runtime:{runtime_code}")
    if outer_timed_out:
        values.append(f"outer-watchdog:{OUTER_WATCHDOG_SECONDS}s")
    return tuple(values)
