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
from contextlib import contextmanager
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[2]
OUTER_WATCHDOG_SECONDS = 360


def isolated_subject_command(
    run_root: Path,
    targets: dict[str, Path],
    runtime_snapshot: Path,
    argv: list[str],
    *,
    broker_socket: Path | None = None,
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
    if broker_socket is not None:
        broker_socket = Path(broker_socket)
        command.extend(
            [
                "--dir",
                "/tmp/check-contract-broker",
                "--ro-bind",
                str(broker_socket.parent),
                "/tmp/check-contract-broker",
                "--setenv",
                "CHECK_CONTRACT_BROKER_SOCKET",
                "/tmp/check-contract-broker/" + broker_socket.name,
                "--setenv",
                "CHECK_CONTRACT_CLIENT_ROOT",
                "/tmp/workspace/.contract-client",
                "--ro-bind",
                "/dev/null",
                "/tmp/check-contract-broker-required",
                "--tmpfs",
                str(SKILLS_ROOT),
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


def terminal_order(*, runtime_code, outer_timed_out):
    values = []
    if runtime_code is not None:
        values.append(f"runtime:{runtime_code}")
    if outer_timed_out:
        values.append(f"outer-watchdog:{OUTER_WATCHDOG_SECONDS}s")
    return tuple(values)
