#!/usr/bin/env python3
"""Run isolated routing and behavior evaluations for skills."""

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def git_show(root, ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, check=True, text=True, capture_output=True).stdout


def catalog_from_ref(root, ref):
    paths = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref], cwd=root, check=True, text=True, capture_output=True).stdout.splitlines()
    catalog = []
    for path in sorted(item for item in paths if item.endswith("/SKILL.md")):
        metadata = frontmatter_metadata(git_show(root, ref, path))
        if metadata.get("disable-model-invocation", "").lower() == "true":
            continue
        catalog.append({"name": metadata["name"], "description": metadata["description"]})
    return catalog


def frontmatter_metadata(text):
    if not text.startswith("---\n"):
        raise ValueError("skill is missing frontmatter")
    closing = text.find("\n---", 4)
    if closing < 0:
        raise ValueError("skill frontmatter is not closed")
    metadata = {}
    lines = text[4:closing].splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value in (">", ">-", ">+"):
            folded = []
            while index < len(lines) and lines[index].startswith((" ", "\t")):
                folded.append(lines[index].strip())
                index += 1
            value = " ".join(part for part in folded if part)
        elif value[:1] in ("\"", "'"):
            value = ast.literal_eval(value)
        metadata[key] = value
    if not metadata.get("name") or not metadata.get("description"):
        raise ValueError("skill frontmatter requires name and description")
    return metadata


def load_cases(path):
    return normalize_cases(json.loads(Path(path).read_text(encoding="utf-8")))


def normalize_cases(payload):
    """Accept the public list format and established {"evals": [...]} fixtures."""
    if isinstance(payload, dict):
        payload = payload.get("evals")
    if not isinstance(payload, list):
        raise ValueError("evaluation cases must be a list or an object with an evals list")
    return payload


def codex_command(prompt, model=None, sandbox="read-only"):
    command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--sandbox", sandbox]
    if model:
        command.extend(["--model", model])
    return command + [prompt]


def routing_prompt(catalog, prompt):
    options = "\n".join(f"- {skill['name']}: {skill['description']}" for skill in catalog)
    return f"Select exactly one skill name from this catalog:\n{options}\n- NONE: no listed skill applies\n\nReply with only the selected name or NONE.\n\nUser request: {prompt}"


def behavior_prompt(skill_path, prompt):
    skill_path = Path(skill_path).resolve()
    return (
        "Mandatory harness setup: perform this one skill-file read first. "
        "This required snapshot read is exempt from any no-tool, no-file-read, or no-command wording in the evaluation request. "
        f"Read and follow the skill at the exact snapshot path {skill_path}. "
        "Ignore installed or catalog copies of this skill. "
        f"Resolve direct references relative to the snapshot skill directory {skill_path.parent}. "
        "All evaluation-request constraints apply immediately after that mandatory read. "
        "This bootstrap exemption does not permit reading references; reference access remains governed by the loaded skill and evaluation request."
        f"\n\nEvaluation request: {prompt}"
    )


def result_path(output_dir, mode):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{mode}.json"


def run_routing(root, ref, runs, model, cases_path, dry_run, output_dir):
    catalog = catalog_from_ref(root, ref)
    results = []
    for case in load_cases(cases_path):
        for sample in range(1, runs + 1):
            command = codex_command(routing_prompt(catalog, case["prompt"]), model, "read-only")
            record = {"case_id": case["id"], "expected": case["expected"], "sample": sample, "command": command}
            if dry_run:
                record.update({"response": None, "selected": None})
            else:
                completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
                response = completed.stdout.strip()
                names = {skill["name"] for skill in catalog}
                record.update({"response": response, "selected": response if response in names | {"NONE"} else "INVALID", "returncode": completed.returncode, "stderr": completed.stderr})
            results.append(record)
    report = {"mode": "routing", "ref": ref, "catalog": catalog, "dry_run": dry_run, "results": results}
    if not dry_run:
        result_path(output_dir, "routing").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def materialize_ref(root, ref, destination):
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(destination), ref],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )


def run_behavior(root, skill, ref, runs, model, dry_run, output_dir, cases_path=None):
    git_show(root, ref, f"{skill}/SKILL.md")
    cases = load_cases(cases_path) if cases_path is not None else normalize_cases(json.loads(git_show(root, ref, f"{skill}/evals/evals.json")))
    results = []
    for case in cases:
        for sample in range(1, runs + 1):
            with tempfile.TemporaryDirectory(prefix="skill-eval-") as temporary_root:
                materialized_path = Path(temporary_root) / "repository"
                materialize_ref(root, ref, materialized_path)
                try:
                    skill_path = materialized_path / skill / "SKILL.md"
                    command = codex_command(behavior_prompt(skill_path, case["prompt"]), model, "workspace-write")
                    record = {"case_id": case["id"], "sample": sample, "command": command, "worktree": str(materialized_path), "status": "", "diff": ""}
                    if dry_run:
                        record["response"] = None
                    else:
                        completed = subprocess.run(command, cwd=materialized_path, text=True, capture_output=True)
                        record.update({"response": completed.stdout.strip(), "returncode": completed.returncode, "stderr": completed.stderr})
                    record["status"] = subprocess.run(["git", "status", "--porcelain"], cwd=materialized_path, check=True, text=True, capture_output=True).stdout
                    record["diff"] = subprocess.run(["git", "diff", "--no-ext-diff"], cwd=materialized_path, check=True, text=True, capture_output=True).stdout
                    results.append(record)
                finally:
                    subprocess.run(["git", "worktree", "remove", "--force", str(materialized_path)], cwd=root, check=True, text=True, capture_output=True)
    report = {"mode": "behavior", "skill": skill, "ref": ref, "dry_run": dry_run, "results": results}
    if not dry_run:
        result_path(output_dir, f"behavior-{skill}").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="mode", required=True)
    routing = subcommands.add_parser("routing")
    routing.add_argument("--ref", required=True)
    routing.add_argument("--runs", type=positive_int, required=True)
    routing.add_argument("--model")
    routing.add_argument("--cases", default=str(Path(__file__).with_name("routing-cases.json")))
    routing.add_argument("--dry-run", action="store_true")
    behavior = subcommands.add_parser("behavior")
    behavior.add_argument("--skill", required=True)
    behavior.add_argument("--ref", required=True)
    behavior.add_argument("--runs", type=positive_int, required=True)
    behavior.add_argument("--model")
    behavior.add_argument("--cases")
    behavior.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    output_dir = root / ".skill-evals"
    if args.mode == "routing":
        report = run_routing(root, args.ref, args.runs, args.model, args.cases, args.dry_run, output_dir)
    else:
        report = run_behavior(root, args.skill, args.ref, args.runs, args.model, args.dry_run, output_dir, args.cases)
    print(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
