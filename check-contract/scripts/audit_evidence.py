"""Strict approved-contract parsing and deterministic Git-object evidence."""

import base64
import hashlib
import importlib.util
import io
import os
import re
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from audit_paths import AuditPathError, PathPolicy, parse_name_status_z


CONTRACT_STATE = (
    Path(__file__).resolve().parents[2]
    / "change-contract"
    / "scripts"
    / "contract_state.py"
)
SECTION_ORDER = (
    "Outcome",
    "Required behaviors",
    "Explicit non-goals",
    "Invariants and risk boundaries",
    "Expected public contracts and side effects",
    "Reuse evidence",
    "Expected change surface",
    "Complexity budget",
    "Acceptance evidence",
    "Unresolved decisions",
)
SECTION_FAMILIES = {
    "Required behaviors": "B",
    "Explicit non-goals": "N",
    "Invariants and risk boundaries": "I",
    "Expected public contracts and side effects": "C",
    "Reuse evidence": "R",
}
COMPLEXITY_IDS = {
    "New modules": "K-MODULES",
    "New runtime dependencies": "K-DEPENDENCIES",
    "New abstractions": "K-ABSTRACTIONS",
    "New configuration": "K-CONFIGURATION",
    "New public interfaces": "K-PUBLIC-INTERFACES",
}
STOPWORDS = frozenset(
    {
        "add",
        "and",
        "are",
        "can",
        "for",
        "from",
        "has",
        "new",
        "none",
        "not",
        "only",
        "return",
        "the",
        "this",
        "through",
        "use",
        "with",
    }
)
QUERY_TOKEN_CAP = 128
REUSE_RESULT_CAP = 2 * 1024 * 1024


class AuthorityError(RuntimeError):
    pass


class ContractParseError(RuntimeError):
    pass


class EvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContractClause:
    clause_id: str
    section: str
    text: str


@dataclass(frozen=True)
class ParsedContract:
    clauses: tuple[ContractClause, ...]
    reuse_query_text: str

    @property
    def clause_ids(self):
        return tuple(clause.clause_id for clause in self.clauses)


@dataclass(frozen=True)
class CommandResult:
    stdout: bytes
    truncated: bool
    timed_out: bool


class LocalGitRunner:
    """Run fixed no-shell Git argv with deadline and bounded result storage."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock

    def run(self, args, *, cwd, deadline, output_limit=None):
        remaining = deadline - self.clock()
        if remaining <= 0:
            return CommandResult(b"", False, True)
        with tempfile.TemporaryFile() as output:
            try:
                process = subprocess.run(
                    ["git", *args],
                    cwd=cwd,
                    check=False,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    timeout=remaining,
                )
            except subprocess.TimeoutExpired:
                return CommandResult(b"", False, True)
            if process.returncode not in (0, 1 if args[:1] == ["grep"] else 0):
                detail = process.stderr.decode("utf-8", "replace").strip()
                raise EvidenceError(f"git {args[0]} failed: {detail}")
            size = output.tell()
            output.seek(0)
            limit = size if output_limit is None else min(size, output_limit)
            return CommandResult(
                output.read(limit),
                output_limit is not None and size > output_limit,
                False,
            )


def _contract_state_module():
    spec = importlib.util.spec_from_file_location(
        "_audit_contract_state",
        CONTRACT_STATE,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def resolve_authority(repo: Path, branch: str, ticket: str) -> dict:
    module = _contract_state_module()
    try:
        result = module.resolve_consumer(
            repo,
            branch,
            ticket,
            allow_missing_ledger=True,
        )
    except (module.ContractStateError, OSError, ValueError) as error:
        raise AuthorityError(str(error)) from error
    if result["state"] != "approved":
        raise AuthorityError("approved contract authority is absent")
    return result


def _sections(text: str) -> dict[str, list[str]]:
    found = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            if current not in SECTION_ORDER:
                raise ContractParseError(f"unknown contract section: {current}")
            if current in found:
                raise ContractParseError(
                    f"duplicate contract section: {current}"
                )
            found[current] = []
        elif current is not None:
            found[current].append(line)
    if tuple(found) != SECTION_ORDER:
        raise ContractParseError("contract sections are missing or out of order")
    return found


def _content(lines: list[str], section: str) -> list[str]:
    values = [line.strip() for line in lines if line.strip()]
    if not values:
        raise ContractParseError(f"empty contract section: {section}")
    return values


def _numbered(lines: list[str], section: str, family: str):
    values = []
    for line in _content(lines, section):
        match = re.fullmatch(rf"- ({family}[1-9][0-9]*):\s+(.+)", line)
        if match is None:
            raise ContractParseError(f"malformed {family} clause in {section}")
        values.append((match.group(1), match.group(2).strip()))
    expected = [f"{family}{index}" for index in range(1, len(values) + 1)]
    if [item[0] for item in values] != expected:
        raise ContractParseError(f"{family} clause IDs must be sequential")
    return values


def parse_contract(contract_bytes: bytes) -> ParsedContract:
    try:
        text = contract_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractParseError("contract must be UTF-8") from error
    sections = _sections(text)
    clauses = []
    outcome = " ".join(_content(sections["Outcome"], "Outcome"))
    clauses.append(ContractClause("O1", "Outcome", outcome))
    by_section = {}
    for section, family in SECTION_FAMILIES.items():
        values = _numbered(sections[section], section, family)
        by_section[section] = values
        clauses.extend(
            ContractClause(clause_id, section, value)
            for clause_id, value in values
        )
    surfaces = []
    for line in _content(
        sections["Expected change surface"],
        "Expected change surface",
    ):
        match = re.fullmatch(r"- (.+)", line)
        if match is None:
            raise ContractParseError("malformed expected-surface clause")
        surfaces.append(match.group(1).strip())
    clauses.extend(
        ContractClause(f"S{index}", "Expected change surface", value)
        for index, value in enumerate(surfaces, 1)
    )
    complexity = []
    for line in _content(sections["Complexity budget"], "Complexity budget"):
        match = re.fullmatch(r"- ([^:]+):\s+(.+)", line)
        if match is None or match.group(1) not in COMPLEXITY_IDS:
            raise ContractParseError("malformed complexity-budget clause")
        complexity.append((match.group(1), match.group(2).strip()))
    if [item[0] for item in complexity] != list(COMPLEXITY_IDS):
        raise ContractParseError("complexity-budget fields are missing or reordered")
    clauses.extend(
        ContractClause(COMPLEXITY_IDS[name], "Complexity budget", value)
        for name, value in complexity
    )
    behaviors = [item[0] for item in by_section["Required behaviors"]]
    acceptance = []
    for line in _content(
        sections["Acceptance evidence"],
        "Acceptance evidence",
    ):
        match = re.fullmatch(r"- (B[1-9][0-9]*)\s+->\s+(.+)", line)
        if match is None:
            raise ContractParseError("malformed acceptance-evidence clause")
        acceptance.append((match.group(1), match.group(2).strip()))
    if [item[0] for item in acceptance] != behaviors:
        raise ContractParseError(
            "acceptance evidence must cover each behavior exactly once"
        )
    clauses.extend(
        ContractClause(f"A-{behavior}", "Acceptance evidence", value)
        for behavior, value in acceptance
    )
    if _content(
        sections["Unresolved decisions"],
        "Unresolved decisions",
    ) != ["- None"]:
        raise ContractParseError("approved contract has unresolved decisions")
    reuse_query_text = "\n".join(
        [outcome]
        + [value for _, value in by_section["Required behaviors"]]
        + [
            value
            for _, value in by_section[
                "Expected public contracts and side effects"
            ]
        ]
        + [value for _, value in by_section["Reuse evidence"]]
        + surfaces
    )
    return ParsedContract(tuple(clauses), reuse_query_text)


def _require(result: CommandResult, operation: str) -> bytes:
    if result.timed_out:
        raise EvidenceError(f"deadline reached during {operation}")
    return result.stdout


def _encoded_bytes(content: bytes) -> dict[str, str]:
    try:
        return {
            "encoding": "utf-8",
            "content": content.decode("utf-8"),
        }
    except UnicodeDecodeError:
        return {
            "encoding": "hex",
            "content": content.hex(),
        }


def _archive_blobs(
    raw: bytes,
    expected_paths: list[str],
) -> tuple[dict[str, object], dict[str, str]]:
    blobs = {}
    guards = {}
    expected = set(expected_paths)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive.getmembers():
            if member.name not in expected:
                continue
            if member.name in blobs:
                raise EvidenceError(
                    "duplicate recorded-HEAD archive entry"
                )
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise EvidenceError(
                        "recorded-HEAD file content is unavailable"
                    )
                content = handle.read()
                encoded = _encoded_bytes(content)
                blobs[member.name] = (
                    encoded["content"]
                    if encoded["encoding"] == "utf-8"
                    else encoded
                )
            elif member.issym():
                content = os.fsencode(member.linkname)
                blobs[member.name] = {
                    "type": "symlink",
                    "target": _encoded_bytes(content),
                }
            else:
                raise EvidenceError(
                    "unsupported recorded-HEAD Git entry type"
                )
            guards[member.name] = hashlib.sha256(content).hexdigest()
    missing = expected - set(blobs)
    if missing:
        raise EvidenceError(
            "recorded-HEAD archive omitted an implementation entry"
        )
    return blobs, guards


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
        if len(token) >= 3 and token.lower() not in STOPWORDS
    }


def _evidence_id(clause: ContractClause) -> str:
    family = clause.clause_id.split("-", 1)[0][0]
    namespace = {
        "O": "behavior",
        "B": "behavior",
        "N": "risk",
        "I": "risk",
        "C": "public-contract",
        "R": "reuse",
        "S": "surface",
        "K": "complexity",
        "A": "acceptance",
    }[family]
    return f"{namespace}:{clause.clause_id}"


def capture_code_evidence(
    authority: dict,
    contract: ParsedContract,
    narrative_paths: tuple[Path, ...],
    runner,
    clock,
    absolute_deadline: float,
) -> dict:
    repo = Path(authority["repository_root"])
    base = authority["base_sha"]
    head = authority["head_sha"]
    try:
        policy = PathPolicy.from_authority(authority, narrative_paths)
    except AuditPathError as error:
        raise EvidenceError(str(error)) from error
    evidence_started = clock()
    available = max(0.0, absolute_deadline - evidence_started)
    reserve = 60.0 if available > 60.0 else 0.0
    evidence_deadline = min(
        evidence_started + 180.0,
        absolute_deadline - reserve,
    )
    status_bytes = _require(
        runner.run(
            ["status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo,
            deadline=evidence_deadline,
        ),
        "initial worktree disclosure",
    )
    inventory_result = runner.run(
        ["diff", "--name-status", "--find-renames", "-z", f"{base}..{head}"],
        cwd=repo,
        deadline=evidence_deadline,
    )
    inventory_bytes = _require(inventory_result, "name inventory")
    try:
        inventory = parse_name_status_z(inventory_bytes)
        included = policy.filter_changed(inventory)
    except AuditPathError as error:
        raise EvidenceError(str(error)) from error
    included_paths = [
        item.path for item in included if not item.status.startswith("D")
    ]
    path_args = [item.path for item in included]
    diff = b""
    blobs = {}
    blob_guards = {}
    if path_args:
        diff = _require(
            runner.run(
                [
                    "diff",
                    "--find-renames",
                    "--no-ext-diff",
                    f"{base}..{head}",
                    "--",
                    *path_args,
                ],
                cwd=repo,
                deadline=evidence_deadline,
            ),
            "implementation diff",
        )
    if included_paths:
        blobs, blob_guards = _archive_blobs(
            _require(
                runner.run(
                    ["archive", "--format=tar", head, "--", *included_paths],
                    cwd=repo,
                    deadline=evidence_deadline,
                ),
                "recorded-HEAD source capture",
            ),
            included_paths,
        )
    diff_text = diff.decode("utf-8", "replace")
    changed_hunks = "\n".join(
        line[1:]
        for line in diff_text.splitlines()
        if line[:1] in {"+", "-"}
        and not line.startswith(("+++", "---"))
    )
    added_hunks = "\n".join(
        line[1:]
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    public_names = re.findall(
        r"^\s*(?:def|class)\s+([A-Za-z][A-Za-z0-9_]*)",
        added_hunks,
        re.MULTILINE,
    )
    query = sorted(
        _tokens(changed_hunks)
        | _tokens(contract.reuse_query_text)
        | _tokens(" ".join(public_names))
    )[:QUERY_TOKEN_CAP]
    tree_bytes = _require(
        runner.run(
            ["ls-tree", "-r", "-z", "--name-only", head],
            cwd=repo,
            deadline=evidence_deadline,
        ),
        "recorded-HEAD path identities",
    )
    denied_paths = frozenset(
        item.path for item in inventory if not policy.accepts_changed(item)
    )
    allowed_paths = policy.allowed_head_paths(tree_bytes, denied_paths)
    grep_args = ["grep", "-n", "-I", "-F", "-z"]
    for token in query:
        grep_args.extend(("-e", token))
    grep_args.extend((head, "--"))
    reuse_result = runner.run(
        grep_args,
        cwd=repo,
        deadline=evidence_deadline,
        output_limit=REUSE_RESULT_CAP,
    )
    reuse_truncated = reuse_result.truncated or reuse_result.timed_out
    try:
        matches = policy.parse_grep_z(
            reuse_result.stdout,
            head,
            allowed_paths,
            allow_incomplete_tail=reuse_truncated,
        )
    except AuditPathError as error:
        raise EvidenceError(str(error)) from error
    changed_paths = []
    for index, item in enumerate(included, 1):
        changed_paths.append(
            {
                "path_id": f"P{index}",
                **item.as_packet_value(),
                "head_blob": blobs.get(item.path),
            }
        )
    packet_inventory = [item.as_packet_value() for item in included]
    evidence = {
        "inventory:NAME-1": {
            "entries": packet_inventory,
            "scope": {"base": base, "head": head},
        },
        "source:CAPTURE-1": {
            "diff": diff_text,
            "head_blobs": blobs,
            "paths": path_args,
        },
        "reuse:SEARCH-1": {
            "query": query,
            "scope": {"commit": head, "tree": "full"},
            "results": [item.as_packet_value() for item in matches],
            "truncated": reuse_truncated,
        },
    }
    for clause in contract.clauses:
        evidence[_evidence_id(clause)] = {
            "clause": clause.text,
            "section": clause.section,
            "capture_refs": ["source:CAPTURE-1", "reuse:SEARCH-1"],
        }
    status = status_bytes.decode("utf-8", "replace")
    return {
        "changed_paths": changed_paths,
        "evidence": evidence,
        "evidence_deadline": evidence_deadline,
        "reuse_truncated": reuse_truncated,
        "worktree": {
            "dirty": bool(status),
            "status": "dirty" if status else "clean",
        },
        "initial_status_bytes_b64": base64.b64encode(
            status_bytes
        ).decode("ascii"),
        "initial_status_sha256": hashlib.sha256(
            status_bytes
        ).hexdigest(),
        "source_guards": {
            "inventory_sha256": hashlib.sha256(
                inventory_bytes
            ).hexdigest(),
            "diff_sha256": hashlib.sha256(diff).hexdigest(),
            "head_blob_sha256": blob_guards,
            "tree_paths_sha256": hashlib.sha256(tree_bytes).hexdigest(),
            "reuse_result_sha256": hashlib.sha256(
                reuse_result.stdout
            ).hexdigest(),
            "base_sha": base,
            "head_sha": head,
        },
        "deferred_narrative_paths": sorted(
            set(policy.narrative_paths)
            | set(policy.deferred_head_narratives(tree_bytes))
            | {
                item.path
                for item in inventory
                if not policy.accepts_changed(item)
                and not policy.is_contract_artifact(item.path)
            }
        ),
    }
