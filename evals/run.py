#!/usr/bin/env python3
"""Run isolated routing and behavior evaluations for skills."""

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path


def git_show(root, ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, check=True, text=True, capture_output=True).stdout


def catalog_from_ref(root, ref):
    paths = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref], cwd=root, check=True, text=True, capture_output=True).stdout.splitlines()
    names = []
    for path in sorted(item for item in paths if item.endswith("/SKILL.md")):
        for line in git_show(root, ref, path).splitlines()[1:]:
            if line == "---":
                break
            if line.startswith("name:"):
                names.append(line.split(":", 1)[1].strip().strip("\"'"))
                break
    return names


def load_cases(path):
    return normalize_cases(json.loads(Path(path).read_text(encoding="utf-8")))


def normalize_cases(payload):
    """Accept the public list format and established {"evals": [...]} fixtures."""
    if isinstance(payload, dict):
        payload = payload.get("evals")
    if not isinstance(payload, list):
        raise ValueError("evaluation cases must be a list or an object with an evals list")
    return payload


def codex_command(prompt, model=None):
    command = ["codex", "exec", "--ephemeral", "--ignore-user-config"]
    if model:
        command.extend(["--model", model])
    return command + [prompt]


def routing_prompt(catalog, prompt):
    options = ", ".join(catalog + ["NONE"])
    return f"Select exactly one skill name from: {options}. Reply with only that name.\n\nUser request: {prompt}"


def result_path(output_dir, mode):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{mode}.json"


def run_routing(root, ref, runs, model, cases_path, dry_run, output_dir):
    catalog = catalog_from_ref(root, ref)
    results = []
    for case in load_cases(cases_path):
        for sample in range(1, runs + 1):
            command = codex_command(routing_prompt(catalog, case["prompt"]), model)
            record = {"case_id": case["id"], "expected": case["expected"], "sample": sample, "command": command}
            if dry_run:
                record.update({"response": None, "selected": None})
            else:
                completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
                response = completed.stdout.strip()
                record.update({"response": response, "selected": response if response in set(catalog + ["NONE"]) else "INVALID", "returncode": completed.returncode, "stderr": completed.stderr})
            results.append(record)
    report = {"mode": "routing", "ref": ref, "catalog": catalog, "dry_run": dry_run, "results": results}
    if not dry_run:
        result_path(output_dir, "routing").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def materialize_ref(root, ref, destination):
    archive = subprocess.run(["git", "archive", ref], cwd=root, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")


def run_behavior(root, skill, ref, runs, model, dry_run, output_dir):
    cases = normalize_cases(json.loads(git_show(root, ref, f"{skill}/evals/evals.json")))
    results = []
    for case in cases:
        for sample in range(1, runs + 1):
            with tempfile.TemporaryDirectory(prefix="skill-eval-") as materialized:
                materialized_path = Path(materialized)
                materialize_ref(root, ref, materialized_path)
                command = codex_command(case["prompt"], model)
                record = {"case_id": case["id"], "sample": sample, "command": command, "worktree": str(materialized_path), "status": "", "diff": ""}
                if dry_run:
                    record["response"] = None
                else:
                    completed = subprocess.run(command, cwd=materialized_path, text=True, capture_output=True)
                    record.update({"response": completed.stdout.strip(), "returncode": completed.returncode, "stderr": completed.stderr})
                record["status"] = subprocess.run(["git", "status", "--porcelain"], cwd=materialized_path, text=True, capture_output=True).stdout
                record["diff"] = subprocess.run(["git", "diff", "--no-ext-diff"], cwd=materialized_path, text=True, capture_output=True).stdout
                results.append(record)
    report = {"mode": "behavior", "skill": skill, "ref": ref, "dry_run": dry_run, "results": results}
    if not dry_run:
        result_path(output_dir, f"behavior-{skill}").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="mode", required=True)
    routing = subcommands.add_parser("routing")
    routing.add_argument("--ref", required=True)
    routing.add_argument("--runs", type=int, required=True)
    routing.add_argument("--model")
    routing.add_argument("--cases", default=str(Path(__file__).with_name("routing-cases.json")))
    routing.add_argument("--dry-run", action="store_true")
    behavior = subcommands.add_parser("behavior")
    behavior.add_argument("--skill", required=True)
    behavior.add_argument("--ref", required=True)
    behavior.add_argument("--runs", type=int, required=True)
    behavior.add_argument("--model")
    behavior.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    output_dir = root / ".skill-evals"
    if args.mode == "routing":
        report = run_routing(root, args.ref, args.runs, args.model, args.cases, args.dry_run, output_dir)
    else:
        report = run_behavior(root, args.skill, args.ref, args.runs, args.model, args.dry_run, output_dir)
    print(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
