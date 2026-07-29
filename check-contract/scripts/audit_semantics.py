"""Canonical packet semantics and immutable Git-object chronology."""

import ast
import hashlib
import json
import re
from collections.abc import Mapping

from audit_domain import clause_family
from audit_evidence import EvidenceError
from audit_paths import parse_name_status_z


SEMANTIC_SCHEMA_VERSION = 1
CHRONOLOGY_SCHEMA_VERSION = 1


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _generation(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def canonical_clause_id(value, aliases):
    return aliases.get(value, value)


def resolve_affected_clause_ids(value, issued_clause_ids, aliases):
    issued = set(issued_clause_ids)
    resolved = []
    unknown = []
    for token in (item.strip() for item in value.split(",")):
        if not token:
            continue
        clause_id = canonical_clause_id(token, aliases)
        if clause_id in issued:
            resolved.append(clause_id)
        else:
            unknown.append(token)
    return {
        "affected_clause_ids": list(dict.fromkeys(resolved)),
        "affected_clause_resolution": (
            "RESOLVED" if resolved and not unknown else "INDETERMINATE"
        ),
        "unresolved_affected_clauses": sorted(set(unknown)),
    }


def _generic_deviation_family(item):
    if item["source_kind"] == "surface":
        return "S"
    if item["source_kind"] != "explicit":
        return None
    namespaces = {
        evidence_id.partition(":")[0] for evidence_id in item["evidence_ids"]
    }
    families = {
        family
        for namespace, family in (
            ("reuse", "R"),
            ("surface", "S"),
            ("complexity", "K"),
        )
        if namespace in namespaces
    }
    return next(iter(families)) if len(families) == 1 else None


def _evidence_stable_clauses(item, aliases):
    candidates = set()
    families = {"reuse": "R", "surface": "S", "complexity": "K"}
    for evidence_id in item["evidence_ids"]:
        namespace, separator, raw_id = evidence_id.partition(":")
        if not separator or namespace not in families:
            continue
        clause_id = canonical_clause_id(raw_id, aliases)
        if clause_family(clause_id) == families[namespace]:
            candidates.add(clause_id)
    return frozenset(candidates)


def classify_deviations(deviations, semantic_contract, boundary_changes):
    aliases = semantic_contract["stable_id_aliases"]
    unbounded = set(
        semantic_contract["ledger_reconciliation"]["unbounded_clause_ids"]
    )
    values = []
    for item in deviations:
        source_id = canonical_clause_id(item["source_id"], aliases)
        family = clause_family(source_id) if source_id else ""
        evidence_clauses = _evidence_stable_clauses(item, aliases)
        stable_id = source_id if family in {"R", "S", "K"} else None
        if stable_id is None and len(evidence_clauses) == 1:
            stable_id = next(iter(evidence_clauses))
        if stable_id is not None:
            family = clause_family(stable_id)
        stable_family = family if stable_id is not None else _generic_deviation_family(item)
        if (
            stable_id in unbounded
            or boundary_changes.get(stable_id, False)
            or any(item in unbounded for item in evidence_clauses)
            or any(boundary_changes.get(item, False) for item in evidence_clauses)
        ):
            boundedness = "UNBOUNDED"
        elif len(evidence_clauses) > 1:
            boundedness = "INDETERMINATE"
        elif stable_id is not None or stable_family is not None:
            boundedness = "BOUNDED"
        else:
            boundedness = "INDETERMINATE"
        values.append(
            {
                "deviation_id": item["deviation_id"],
                "stable_clause_id": stable_id,
                "stable_clause_family": stable_family,
                "boundedness": boundedness,
            }
        )
    return values


def _source(value):
    return value if isinstance(value, str) else None


def _tree(source):
    try:
        return ast.parse(source)
    except (SyntaxError, TypeError, ValueError):
        return None


def _definitions(source):
    tree = _tree(source)
    if tree is None:
        return ()
    return tuple(
        ("function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class", node.name)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )


def _call_targets(source):
    tree = _tree(source)
    if tree is None:
        return frozenset()
    values = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            values.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            parts = []
            value = node.func
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.append(value.id)
                values.add(".".join(reversed(parts)))
    return frozenset(values)


def _module_name(path):
    if not path.endswith(".py"):
        return None
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else None


def _import_from_module(node, use_path):
    if node.level == 0:
        return node.module
    use_module = _module_name(use_path)
    if use_module is None:
        return None
    package = (
        use_module
        if use_path.endswith("/__init__.py")
        else use_module.rpartition(".")[0]
    )
    parts = package.split(".") if package else []
    parent_count = node.level - 1
    if parent_count > len(parts):
        return None
    base = parts[: len(parts) - parent_count]
    suffix = node.module.split(".") if node.module else []
    values = base + suffix
    return ".".join(values) if values else None


def _uses_helper(source, use_path, definition_path, name):
    tree = _tree(source)
    if tree is None:
        return False
    targets = _call_targets(source)
    if use_path == definition_path:
        return name in targets
    module = _module_name(definition_path)
    if module is None:
        return False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if _import_from_module(node, use_path) != module:
                continue
            for imported in node.names:
                if imported.name == name:
                    return (imported.asname or name) in targets
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name != module:
                    continue
                prefix = imported.asname or module
                if f"{prefix}.{name}" in targets:
                    return True
    return False


def _implementation_path(path):
    parts = path.split("/")
    name = parts[-1]
    return "tests" not in parts and not name.startswith(("test_", "spec_"))


def _git(runner, repo, deadline, *args):
    result = runner.run(
        list(args), cwd=repo, deadline=deadline, output_limit=4 * 1024 * 1024
    )
    if result.timed_out or result.truncated:
        raise EvidenceError(f"git {args[0]} chronology capture was incomplete")
    return result.stdout


def _source_at(runner, repo, deadline, commit, path):
    try:
        return _git(runner, repo, deadline, "show", f"{commit}:{path}").decode(
            "utf-8"
        )
    except (EvidenceError, UnicodeDecodeError):
        return None


def _required_source_at(runner, repo, deadline, commit, path):
    try:
        value = _git(
            runner, repo, deadline, "show", f"{commit}:{path}"
        ).decode("utf-8")
    except (EvidenceError, UnicodeDecodeError):
        return None, False
    return value, True


def _source_model(authority, captured, runner, deadline):
    repo = authority["repository_root"]
    base = authority["base_sha"]
    head_sources = {}
    base_sources = {}
    base_resolution = {}
    path_ids = {}
    for item in captured["changed_paths"]:
        path = item["path"]
        path_ids[path] = item["path_id"]
        head = _source(item.get("head_blob"))
        if head is not None:
            head_sources[path] = head
        base_path = item.get("old_path", path)
        if not item["status"].startswith("A"):
            base_source, resolved = _required_source_at(
                runner, repo, deadline, base, base_path
            )
            if base_source is not None:
                base_sources[path] = base_source
            base_resolution[path] = resolved
        else:
            base_resolution[path] = True

    changed_paths = frozenset(head_sources)
    reuse_results = captured["evidence"]["reuse:SEARCH-1"]["results"]
    helper_candidate_paths = {
        item["path"]
        for item in reuse_results
        if _implementation_path(item["path"])
        and re.match(r"(?:async\s+def|def|class)\s+", item["text"])
    }
    for path in sorted(helper_candidate_paths - set(head_sources)):
        head_source = _source_at(
            runner, repo, deadline, authority["head_sha"], path
        )
        if head_source is None:
            continue
        head_sources[path] = head_source
        base_source, resolved = _required_source_at(
            runner, repo, deadline, base, path
        )
        if base_source is not None:
            base_sources[path] = base_source
        base_resolution[path] = resolved

    base_definitions = {
        (path, kind, name)
        for path, source in base_sources.items()
        for kind, name in _definitions(source)
    }
    head_definitions = {
        (path, kind, name)
        for path, source in head_sources.items()
        if _implementation_path(path)
        for kind, name in _definitions(source)
    }
    base_definitions = {
        item for item in base_definitions if _implementation_path(item[0])
    }
    helpers = []
    for index, (path, kind, name) in enumerate(sorted(head_definitions), 1):
        used_by = sorted(
            path_ids[used_path]
            for used_path, source in head_sources.items()
            if used_path in path_ids
            and _implementation_path(used_path)
            and _uses_helper(source, used_path, path, name)
        )
        helpers.append(
            {
                "fact_id": f"H{index}",
                "name": name,
                "kind": kind.upper(),
                "definition_path_id": path_ids.get(path),
                "definition_path": path,
                "existed_at_approval_base": (
                    (path, kind, name) in base_definitions
                    if base_resolution.get(path, False)
                    else None
                ),
                "use_status": "USED" if used_by else "NOT_USED",
                "used_by_path_ids": used_by,
                "evidence_ids": (
                    ["source:CAPTURE-1", "reuse:SEARCH-1"]
                    if path in path_ids
                    else ["reuse:SEARCH-1"]
                ),
            }
        )
    return {
        "head_sources": head_sources,
        "base_sources": base_sources,
        "path_ids": path_ids,
        "helpers": helpers,
        "new_definitions": {
            item
            for item in head_definitions - base_definitions
            if item[0] in changed_paths
        },
        "analysis_complete": all(
            base_resolution.get(path, False)
            for path, source in head_sources.items()
            if path in changed_paths
            and _implementation_path(path)
            and _tree(source) is not None
        ),
    }


def _cap(text):
    match = re.match(r"\s*(\d+)", text)
    return int(match.group(1)) if match else None


def _allowed_public_names(contract):
    clause = next(
        (
            item
            for item in contract.clauses
            if item.clause_id == "K-PUBLIC-INTERFACES"
        ),
        None,
    )
    if clause is None:
        return frozenset()
    return frozenset(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", clause.text))


def _issued_clause_facts(contract, model):
    if not model["analysis_complete"]:
        return {}
    clauses = {item.clause_id: item for item in contract.clauses}
    allowed_public = _allowed_public_names(contract)
    new_abstractions = sorted(
        f"{path}:{kind}:{name}"
        for path, kind, name in model["new_definitions"]
        if not (kind == "function" and name in allowed_public)
    )
    clause = clauses.get("K-ABSTRACTIONS")
    facts = {}
    if clause is not None:
        cap = _cap(clause.text)
        if cap is not None and len(new_abstractions) > cap:
            facts["K-ABSTRACTIONS"] = {
                "measurement": "UPPER_BOUND",
                "cap": cap,
                "actual": len(new_abstractions),
                "status": "EXCEEDED",
                "item_ids": new_abstractions,
                "evidence_ids": ["source:CAPTURE-1"],
                "reason": "The measured abstraction count exceeds the issued cap.",
            }
    return facts


def build_semantics(contract, rules, model):
    value = {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        **_plain(rules.semantic_contract),
        "issued_facts": {
            "clause_statuses": _issued_clause_facts(contract, model),
            "helpers": model["helpers"],
        },
    }
    value["generation"] = _generation(value)
    return value


def _contains_definition(source, helper):
    if source is None:
        return False
    return (helper["kind"].lower(), helper["name"]) in _definitions(source)


def _contains_helper_use(source, use_path, helper):
    return source is not None and _uses_helper(
        source,
        use_path,
        helper["definition_path"],
        helper["name"],
    )


def _indeterminate_chronology(base, head, helpers, reason):
    value = {
        "schema_version": CHRONOLOGY_SCHEMA_VERSION,
        "status": "INDETERMINATE",
        "unknown_reason": reason,
        "approval_base_sha": base,
        "head_sha": head,
        "commits": [],
        "path_facts": [],
        "helper_facts": [
            {
                **item,
                "introduced_commit": None,
                "affected_implementation_commits": [],
                "relation": "INDETERMINATE",
            }
            for item in helpers
        ],
    }
    value["generation"] = _generation(value)
    return value


def build_chronology(authority, captured, model, runner, deadline):
    repo = authority["repository_root"]
    base = authority["base_sha"]
    head = authority["head_sha"]
    helpers = model["helpers"]
    try:
        raw = _git(
            runner,
            repo,
            deadline,
            "rev-list",
            "--reverse",
            "--topo-order",
            "--parents",
            f"{base}..{head}",
        ).decode("ascii")
        records = [line.split() for line in raw.splitlines() if line]
        if not records or any(
            len(record) != 2
            or re.fullmatch(r"[0-9a-f]{40}", record[0]) is None
            or re.fullmatch(r"[0-9a-f]{40}", record[1]) is None
            for record in records
        ):
            return _indeterminate_chronology(
                base, head, helpers, "MERGE_OR_AMBIGUOUS_ANCESTRY"
            )
        expected_parent = base
        for commit, parent in records:
            if parent != expected_parent:
                return _indeterminate_chronology(
                    base, head, helpers, "MERGE_OR_AMBIGUOUS_ANCESTRY"
                )
            expected_parent = commit
        if records[-1][0] != head:
            return _indeterminate_chronology(
                base, head, helpers, "MERGE_OR_AMBIGUOUS_ANCESTRY"
            )

        known_paths = model["path_ids"]
        commits = []
        for commit, parent in records:
            changed = parse_name_status_z(
                _git(
                    runner,
                    repo,
                    deadline,
                    "diff-tree",
                    "--no-commit-id",
                    "--name-status",
                    "--find-renames",
                    "-r",
                    "-z",
                    parent,
                    commit,
                )
            )
            paths = sorted(
                (
                    {"path_id": known_paths[item.path], "path": item.path}
                    for item in changed
                    if item.path in known_paths
                ),
                key=lambda item: item["path_id"],
            )
            commits.append(
                {
                    "commit_sha": commit,
                    "parent_sha": parent,
                    "changed_paths": paths,
                }
            )

        order = {commit: index for index, (commit, _) in enumerate(records)}
        helper_values = []
        for helper in helpers:
            definition_path = helper["definition_path"]
            introduced = None
            if helper["existed_at_approval_base"] is False:
                for commit, _ in records:
                    if _contains_definition(
                        _source_at(
                            runner, repo, deadline, commit, definition_path
                        ),
                        helper,
                    ):
                        introduced = commit
                        break
            affected = []
            for path_id in helper["used_by_path_ids"]:
                use_path = next(
                    path
                    for path, issued_id in known_paths.items()
                    if issued_id == path_id
                )
                for commit, _ in records:
                    if _contains_helper_use(
                        _source_at(runner, repo, deadline, commit, use_path),
                        use_path,
                        helper,
                    ):
                        affected.append(commit)
                        break
            affected = sorted(set(affected), key=order.get)
            if helper["existed_at_approval_base"] is True:
                relation = "EXISTED_AT_APPROVAL_BASE"
            elif helper["existed_at_approval_base"] is None:
                relation = "INDETERMINATE"
            elif introduced is None or not affected:
                relation = "INDETERMINATE"
            elif order[introduced] < order[affected[0]]:
                relation = "INTRODUCED_BEFORE_AFFECTED_IMPLEMENTATION"
            elif order[introduced] == order[affected[0]]:
                relation = "INTRODUCED_BY_AFFECTED_IMPLEMENTATION"
            else:
                relation = "INTRODUCED_LATER"
            helper_values.append(
                {
                    **helper,
                    "introduced_commit": introduced,
                    "affected_implementation_commits": affected,
                    "relation": relation,
                }
            )

        path_values = []
        for item in captured["changed_paths"]:
            introduced = None
            if item["status"].startswith("A"):
                for commit in commits:
                    if any(
                        path["path_id"] == item["path_id"]
                        for path in commit["changed_paths"]
                    ):
                        introduced = commit["commit_sha"]
                        break
            path_values.append(
                {
                    "path_id": item["path_id"],
                    "path": item["path"],
                    "existed_at_approval_base": not item["status"].startswith("A"),
                    "introduced_commit": introduced,
                }
            )
        value = {
            "schema_version": CHRONOLOGY_SCHEMA_VERSION,
            "status": "DETERMINATE",
            "unknown_reason": None,
            "approval_base_sha": base,
            "head_sha": head,
            "commits": commits,
            "path_facts": path_values,
            "helper_facts": helper_values,
        }
    except (EvidenceError, UnicodeDecodeError, ValueError):
        return _indeterminate_chronology(
            base, head, helpers, "CHRONOLOGY_EVIDENCE_INCOMPLETE"
        )
    value["generation"] = _generation(value)
    return value


def issue_runtime_contract(authority, contract, captured, rules, runner, deadline):
    model = _source_model(authority, captured, runner, deadline)
    return (
        build_semantics(contract, rules, model),
        build_chronology(authority, captured, model, runner, deadline),
    )
