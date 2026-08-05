#!/usr/bin/env python3
"""Deterministic quality checks for the tracked skill library."""

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path


START = "<!-- SKILL-CATALOG:START -->"
END = "<!-- SKILL-CATALOG:END -->"
DESCRIPTION_LIMIT = 320
LINK_RE = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
LEAK_PATTERNS = (
    r"\b(?:first|then|finally)\b",
    r"`[^`]+`",
    r"(?:^|\s)(?:\.?\.?/|[\w.-]+/[\w./-]+)",
    r"\b\d+\s+(?:agents?|workers?)\b",
    r"\b(?:write|writes|writing|output)\b.{0,30}\b(?:path|file|\.md|\.json)\b",
)


def discover_skill_paths(root):
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", "*/SKILL.md"],
        check=True,
        text=True,
        capture_output=True,
    )
    return sorted(path for path in result.stdout.splitlines() if path)


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")
    closing = text.find("\n---", 4)
    if closing < 0:
        raise ValueError("missing closing frontmatter delimiter")
    lines = text[4:closing].splitlines()
    data = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z][\w-]*):[ \t]*(.*)", line)
        if not match:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = match.groups()
        if value in (">", ">-", ">+"):
            folded = []
            while index < len(lines) and (lines[index].startswith(" ") or lines[index].startswith("\t")):
                folded.append(lines[index].strip())
                index += 1
            value = " ".join(part for part in folded if part)
        elif value[:1] in ("'", '"'):
            try:
                value = ast.literal_eval(value)
            except (SyntaxError, ValueError) as error:
                raise ValueError(f"invalid quoted value for {key}") from error
        data[key] = value
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError("missing name")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        raise ValueError("missing description")
    return data


def body_metrics(text):
    closing = text.find("\n---", 4)
    body = text[closing + 4:] if closing >= 0 else text
    return {"body_characters": len(body), "body_words": len(re.findall(r"\S+", body))}


def local_link_errors(root, relative_path, text):
    errors = []
    source = root / relative_path
    for raw_target in LINK_RE.findall(text):
        target = raw_target.split("#", 1)[0].strip()
        if not target or re.match(r"[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("/"):
            continue
        if not (source.parent / target).exists():
            errors.append(f"{relative_path}: broken local link: {raw_target}")
    return errors


def catalog_table(skills):
    lines = ["| Skill | Description |", "|-------|-------------|"]
    for skill in sorted(skills, key=lambda item: item["name"]):
        description = skill["description"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{skill['name']}` | {description} |")
    return "\n".join(lines)


def catalog_block(readme):
    start = readme.find(START)
    end = readme.find(END)
    if start < 0 or end < 0 or end < start:
        return None
    return readme[start + len(START):end].strip("\n")


def check(root):
    root = Path(root)
    errors, warnings, skills = [], [], []
    names = {}
    for relative_path in discover_skill_paths(root):
        path = root / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            errors.append(f"{relative_path}: unreadable: {error}")
            continue
        try:
            frontmatter = parse_frontmatter(text)
        except ValueError as error:
            errors.append(f"{relative_path}: invalid frontmatter: {error}")
            continue
        name = frontmatter["name"].strip()
        description = frontmatter["description"].strip()
        metrics = body_metrics(text)
        skill = {"path": relative_path, "name": name, "description": description,
                 "description_characters": len(description), **metrics}
        skills.append(skill)
        names.setdefault(name, []).append(relative_path)
        if not description.startswith("Use when"):
            errors.append(f"{relative_path}: description must start with 'Use when'")
        if len(description) > DESCRIPTION_LIMIT:
            errors.append(f"{relative_path}: description exceeds 320 characters ({len(description)})")
        if any(re.search(pattern, description, re.I) for pattern in LEAK_PATTERNS):
            errors.append(f"{relative_path}: implementation leakage in description")
        errors.extend(local_link_errors(root, relative_path, text))
        if metrics["body_characters"] > 8000 or metrics["body_words"] > 1200:
            warnings.append(f"{relative_path}: body observation: {metrics['body_characters']} chars, {metrics['body_words']} words")
    for name, paths in sorted(names.items()):
        if len(paths) > 1:
            errors.append(f"duplicate skill name: {name} ({', '.join(paths)})")
    readme_path = root / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        errors.append(f"README.md: unreadable: {error}")
    else:
        errors.extend(local_link_errors(root, "README.md", readme))
        if catalog_block(readme) != catalog_table(skills):
            errors.append("README catalog drift")
    skills.sort(key=lambda item: item["path"])
    return {
        "inventory_count": len(skills),
        "description_characters": sum(skill["description_characters"] for skill in skills),
        "skills": skills,
        "errors": sorted(errors),
        "warnings": sorted(warnings),
    }


def sync_readme(root):
    root = Path(root)
    readme_path = root / "README.md"
    readme = readme_path.read_bytes()
    result = check(root)
    start_marker = START.encode("utf-8")
    end_marker = END.encode("utf-8")
    start = readme.find(start_marker)
    end = readme.find(end_marker)
    if start < 0 or end < 0 or end < start:
        raise ValueError("README.md is missing managed catalog markers")
    replacement = (START + "\n" + catalog_table(result["skills"]) + "\n" + END).encode("utf-8")
    updated = readme[:start] + replacement + readme[end + len(end_marker):]
    if updated != readme:
        readme_path.write_bytes(updated)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    check_parser = subcommands.add_parser("check")
    check_parser.add_argument("--json", action="store_true")
    subcommands.add_parser("sync-readme")
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.command == "sync-readme":
        try:
            result = sync_readme(root)
        except ValueError as error:
            print(f"skill-quality: {error}", file=sys.stderr)
            return 1
        print(f"synced {result['inventory_count']} skills")
        return 0
    result = check(root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        print(f"inventory: {result['inventory_count']} skills")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
