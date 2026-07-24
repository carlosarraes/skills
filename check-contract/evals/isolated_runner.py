#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
from pathlib import Path

from runner_preflight import validate_pre_run_directory


MASKED_DIRECTORIES = (
    "/home/carraes/projs/skills",
    "/home/carraes/.agents/skills",
    "/home/carraes/.codex",
    "/home/carraes/.claude",
)
MASKED_FILES = ()
MODEL = "claude-sonnet-5"
REASONING_EFFORT = "high"
CREDENTIALS_FILE = "/home/carraes/.claude/.credentials.json"


def build_command(run_root: Path, workdir: str, prompt: str) -> list[str]:
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
        str(run_root.resolve()),
        "/tmp/workspace",
        "--dir",
        "/tmp/home",
        "--dir",
        "/tmp/home/.claude",
        "--ro-bind",
        CREDENTIALS_FILE,
        "/tmp/home/.claude/.credentials.json",
    ]
    for directory in MASKED_DIRECTORIES:
        command.extend(["--tmpfs", directory])
    for path in MASKED_FILES:
        command.extend(["--ro-bind", "/dev/null", path])
    command.extend(
        [
            "--setenv",
            "HOME",
            "/tmp/home",
            "--chdir",
            workdir,
            "claude",
            "-p",
            "--safe-mode",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--permission-mode",
            "bypassPermissions",
            "--model",
            MODEL,
            "--effort",
            REASONING_EFFORT,
            "--output-format",
            "stream-json",
            "--verbose",
            prompt,
        ]
    )
    return command


def run_isolated(
    run_root: Path,
    workdir: str,
    prompt: str,
    rollout_output: Path,
    timeout_seconds: int,
) -> int:
    validate_pre_run_directory(run_root)
    workdir_path = Path(workdir)
    if (
        not workdir_path.is_absolute()
        or ".." in workdir_path.parts
        or not workdir.startswith("/tmp/workspace/fixture/")
    ):
        raise ValueError("workdir must be an absolute audited fixture target")
    if run_root.resolve() in rollout_output.resolve().parents:
        raise ValueError("rollout output must stay outside the agent-visible run root")
    command = build_command(run_root, workdir, prompt)
    rollout_output.parent.mkdir(parents=True, exist_ok=True)
    with rollout_output.open("wb") as output:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            result = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return 124
    if result == 0:
        records = [
            json.loads(line)
            for line in rollout_output.read_text(encoding="utf-8").splitlines()
            if line
        ]
        final = next(
            record["result"]
            for record in reversed(records)
            if record.get("type") == "result"
        )
        (run_root / "final.md").write_text(final, encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--rollout-output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=360)
    args = parser.parse_args()
    return run_isolated(
        args.run_root.resolve(),
        args.workdir,
        args.prompt,
        args.rollout_output.resolve(),
        args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
