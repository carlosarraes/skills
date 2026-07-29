"""Fact-derived semantic golden inputs for materialized check-contract evals.

This module derives fixture judgments only. The production rule pack and
``audit_policy.aggregate`` remain the sole owners of axes, precedence, verdict,
and routing.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping


CHECK_CONTRACT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = CHECK_CONTRACT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_domain import (  # noqa: E402
    AxisItem,
    ClauseJudgment,
    CodeJudgment,
    Deviation,
    DeviationMatch,
    LedgerEntry,
    PathAssessment,
    ReconciliationJudgment,
    RulePack,
    SurfaceJudgment,
    clause_family,
)
from audit_evidence import LocalGitRunner, parse_contract  # noqa: E402
from audit_policy import aggregate  # noqa: E402
from audit_reconciliation import parse_execution_ledger  # noqa: E402
from probe_runner import run_probe  # noqa: E402


CONTRACT = Path(".notes/feature-proj-123/contract")
VERSION = CONTRACT / "v1"
EXPECTED_CLAUSE_IDS = {
    "O1",
    "B1",
    "B2",
    "B3",
    "B4",
    "N1",
    "N2",
    "N3",
    "N4",
    "I1",
    "I2",
    "C1",
    "C2",
    "R1",
    "R2",
    "R3",
    "S1",
    "S2",
    "K-MODULES",
    "K-DEPENDENCIES",
    "K-ABSTRACTIONS",
    "K-CONFIGURATION",
    "K-PUBLIC-INTERFACES",
    "A-B1",
    "A-B2",
    "A-B3",
    "A-B4",
}


@dataclass(frozen=True)
class AcceptanceExample:
    args: tuple[object, ...]
    expected: object | None
    raises: str | None


@dataclass(frozen=True)
class SemanticEvaluation:
    decision: object
    clause_statuses: Mapping[str, str]
    deviation_sources: tuple[str, ...]
    ledger_statuses: Mapping[str, str]
    affected_clauses: Mapping[str, tuple[str, ...]]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sources(repo: Path, revision: str) -> dict[str, str]:
    paths = _git(repo, "ls-tree", "-r", "--name-only", revision).splitlines()
    return {
        path: _git(repo, "show", f"{revision}:{path}")
        for path in paths
        if path.startswith("src/") and path.endswith(".py")
    }


def _class_names(source: str) -> set[str]:
    return {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef)
    }


def derive_n4_status(
    base_sources: Mapping[str, str],
    head_sources: Mapping[str, str],
) -> str:
    """Judge the exact N4 predicate: no class hierarchy and no new module."""
    new_modules = set(head_sources) - set(base_sources)
    if new_modules:
        return "UNMET"

    classes = set()
    trees = {}
    for path, source in head_sources.items():
        trees[path] = ast.parse(source)
        classes.update(_class_names(source))

    for tree in trees.values():
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                name = None
                if isinstance(base, ast.Name):
                    name = base.id
                elif isinstance(base, ast.Attribute):
                    name = base.attr
                if name in classes:
                    return "UNMET"
    return "MET"


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    return next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ),
        None,
    )


def _call_names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    names = set()
    for candidate in ast.walk(node):
        if not isinstance(candidate, ast.Call):
            continue
        if isinstance(candidate.func, ast.Name):
            names.add(candidate.func.id)
        elif isinstance(candidate.func, ast.Attribute):
            names.add(candidate.func.attr)
    return names


def _definition_keys(sources: Mapping[str, str]) -> set[tuple[str, str, str]]:
    definitions = set()
    for path, source in sources.items():
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef):
                definitions.add((path, "function", node.name))
            elif isinstance(node, ast.ClassDef):
                definitions.add((path, "class", node.name))
    return definitions


def _public_functions(sources: Mapping[str, str]) -> set[str]:
    functions = set()
    for path, source in sources.items():
        module = path.removesuffix(".py").replace("/", ".")
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions.add(f"{module}.{node.name}")
    return functions


def _import_roots(sources: Mapping[str, str]) -> set[str]:
    imports = set()
    for source in sources.values():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
    return imports


def _external_imports(sources: Mapping[str, str]) -> set[str]:
    return {
        name
        for name in _import_roots(sources)
        if name != "src" and name not in sys.stdlib_module_names
    }


def _literal(node: ast.AST, environment: Mapping[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in environment:
        return environment[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_literal(node.operand, environment)
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(_literal(item, environment) for item in node.elts)
    raise ValueError("acceptance example is not a static literal")


def _apply_call(
    node: ast.AST,
    environment: Mapping[str, object],
) -> tuple[object, ...] | None:
    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, ast.Name) or node.func.id != "apply_discount":
        return None
    return tuple(_literal(arg, environment) for arg in node.args)


def _acceptance_examples(source: str) -> tuple[AcceptanceExample, ...]:
    examples = []

    def visit_statements(
        statements: list[ast.stmt],
        environment: Mapping[str, object],
        raises: str | None = None,
    ) -> None:
        for statement in statements:
            if isinstance(statement, (ast.ClassDef, ast.FunctionDef)):
                visit_statements(statement.body, environment, raises)
                continue
            if isinstance(statement, ast.For) and isinstance(statement.target, ast.Name):
                for value in _literal(statement.iter, environment):
                    visit_statements(
                        statement.body,
                        {**environment, statement.target.id: value},
                        raises,
                    )
                continue
            if isinstance(statement, ast.With):
                expected_exception = raises
                for item in statement.items:
                    context = item.context_expr
                    if not isinstance(context, ast.Call):
                        continue
                    if not isinstance(context.func, ast.Attribute):
                        continue
                    if context.func.attr != "assertRaises" or not context.args:
                        continue
                    if isinstance(context.args[0], ast.Name):
                        expected_exception = context.args[0].id
                visit_statements(statement.body, environment, expected_exception)
                continue
            if not isinstance(statement, ast.Expr) or not isinstance(
                statement.value, ast.Call
            ):
                continue
            call = statement.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "assertEqual":
                args = _apply_call(call.args[0], environment)
                if args is not None:
                    examples.append(
                        AcceptanceExample(
                            args=args,
                            expected=_literal(call.args[1], environment),
                            raises=None,
                        )
                    )
                continue
            args = _apply_call(call, environment)
            if args is not None and raises is not None:
                examples.append(
                    AcceptanceExample(args=args, expected=None, raises=raises)
                )

    visit_statements(ast.parse(source).body, {})
    return tuple(examples)


_BEHAVIOR_PROGRAM = r"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from src.checkout import apply_discount, checkout_total

def observe(function, *args):
    try:
        return {"kind": "returns", "value": function(*args)}
    except Exception as error:
        return {"kind": "raises", "exception": type(error).__name__}

print(json.dumps({
    "B1": observe(apply_discount, 42.5, 0),
    "B2": observe(apply_discount, 10.01, 50),
    "B3": observe(apply_discount, 10, -1),
    "B4": observe(apply_discount, 10, 101),
    "I1-round": observe(checkout_total, 10.125),
    "I1-negative": observe(checkout_total, -1),
}, sort_keys=True))
""".strip()


def _behavior(repo: Path) -> dict[str, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", _BEHAVIOR_PROGRAM],
        cwd=repo,
        env={
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _budget_cap(text: str) -> int:
    match = re.match(r"(\d+)", text)
    if match is None:
        raise ValueError(f"complexity budget does not start with a count: {text}")
    return int(match.group(1))


def _budget_status(actual: int, clause_text: str) -> str:
    return "MET" if actual <= _budget_cap(clause_text) else "EXCEEDED"


def _authority_valid(repo: Path, base: str) -> bool:
    contract_path = repo / VERSION / "contract.md"
    approval = json.loads((repo / VERSION / "approval.json").read_text())
    return (
        hashlib.sha256(contract_path.read_bytes()).hexdigest()
        == approval.get("contract_sha256")
        and approval.get("base_sha") == base
        and approval.get("branch") == _git(repo, "branch", "--show-current")
        and approval.get("ticket") == "PROJ-123"
        and not _git(repo, "merge-base", "--is-ancestor", base, "HEAD")
    )


def _acceptance_statuses(
    examples: tuple[AcceptanceExample, ...],
) -> dict[str, str]:
    b1 = any(
        len(example.args) == 2
        and example.args[1] == 0
        and example.expected == example.args[0]
        and example.raises is None
        for example in examples
    )
    b2 = False
    for example in examples:
        if len(example.args) != 2 or example.raises is not None:
            continue
        subtotal, percentage = example.args
        if not all(isinstance(value, (int, float)) for value in example.args):
            continue
        if not 0 <= percentage <= 100:
            continue
        raw = subtotal * (1 - percentage / 100)
        rounded = round(raw, 2)
        if raw != rounded and example.expected == rounded:
            b2 = True
    b3 = any(
        len(example.args) == 2
        and isinstance(example.args[1], (int, float))
        and example.args[1] < 0
        and example.raises == "ValueError"
        for example in examples
    )
    b4 = any(
        len(example.args) == 2
        and isinstance(example.args[1], (int, float))
        and example.args[1] > 100
        and example.raises == "ValueError"
        for example in examples
    )
    return {
        "A-B1": "MET" if b1 else "INDETERMINATE",
        "A-B2": "MET" if b2 else "INDETERMINATE",
        "A-B3": "MET" if b3 else "INDETERMINATE",
        "A-B4": "MET" if b4 else "INDETERMINATE",
    }


def _configuration_count(inventory: tuple[tuple[str, str], ...]) -> int:
    configuration_names = {
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        ".env",
    }
    return sum(
        1
        for status, path in inventory
        if status in {"A", "M"}
        and (
            Path(path).name in configuration_names
            or Path(path).suffix in {".yaml", ".yml", ".toml"}
        )
    )


def _inventory(repo: Path, base: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        line.split("\t", 1)
        for line in _git(repo, "diff", "--name-status", f"{base}..HEAD").splitlines()
        if line
    )


def _external_effects(source: str) -> bool:
    risky_imports = {"requests", "httpx", "sqlite3", "socket", "subprocess"}
    risky_calls = {"open", "unlink", "remove", "write_text", "write_bytes"}
    tree = ast.parse(source)
    imports = _import_roots({"src/checkout.py": source})
    return bool(imports & risky_imports or _call_names(tree) & risky_calls)


def _clause_statuses(
    parsed_contract,
    base_sources: Mapping[str, str],
    head_sources: Mapping[str, str],
    tests_source: str,
    inventory: tuple[tuple[str, str], ...],
    behavior: Mapping[str, Mapping[str, object]],
) -> dict[str, str]:
    clauses = {clause.clause_id: clause.text for clause in parsed_contract.clauses}
    if set(clauses) != EXPECTED_CLAUSE_IDS:
        raise ValueError("v3 fixture contract clause IDs are unexpected")

    checkout = head_sources["src/checkout.py"]
    pricing = head_sources["src/pricing.py"]
    checkout_tree = ast.parse(checkout)
    apply_discount = _function(checkout_tree, "apply_discount")
    checkout_total = _function(checkout_tree, "checkout_total")
    base_checkout_total = _function(
        ast.parse(base_sources["src/checkout.py"]),
        "checkout_total",
    )
    calls = _call_names(apply_discount)
    examples = _acceptance_examples(tests_source)
    acceptance = _acceptance_statuses(examples)

    behavior_status = {
        "B1": (
            "MET"
            if behavior["B1"] == {"kind": "returns", "value": 42.5}
            else "UNMET"
        ),
        "B2": (
            "MET"
            if behavior["B2"] == {"kind": "returns", "value": 5.0}
            else "UNMET"
        ),
        "B3": (
            "MET"
            if behavior["B3"] == {"kind": "raises", "exception": "ValueError"}
            else "UNMET"
        ),
        "B4": (
            "MET"
            if behavior["B4"] == {"kind": "raises", "exception": "ValueError"}
            else "UNMET"
        ),
    }
    outcome_status = (
        "MET" if all(status == "MET" for status in behavior_status.values()) else "UNMET"
    )

    changed_source = "\n".join(head_sources.values()).lower()
    new_external_dependencies = _external_imports(head_sources) - _external_imports(
        base_sources
    )
    n2_tokens = ("persist", "feature_flag", "feature flag", "configuration")
    new_public = _public_functions(head_sources) - _public_functions(base_sources)
    expected_public = {"src.checkout.apply_discount"}
    new_definitions = _definition_keys(head_sources) - _definition_keys(base_sources)
    new_abstractions = {
        definition
        for definition in new_definitions
        if not (
            definition[1] == "function"
            and f"{definition[0].removesuffix('.py').replace('/', '.')}.{definition[2]}"
            in expected_public
        )
    }
    new_modules = {
        path
        for status, path in inventory
        if status == "A" and path.startswith("src/") and path.endswith(".py")
    }
    pricing_changed = any(path == "src/pricing.py" for _, path in inventory)
    inline_validation = "percentage < 0 or percentage > 100" in checkout
    helper_used = "_validate_percentage" in calls
    validator_present = "def _validate_percentage(" in pricing
    calculation_present = (
        any(
            isinstance(node, (ast.Mult, ast.Div, ast.Sub))
            for node in ast.walk(apply_discount)
        )
        if apply_discount
        else False
    )

    i1_met = (
        ast.dump(checkout_total, include_attributes=False)
        == ast.dump(base_checkout_total, include_attributes=False)
        and behavior["I1-round"] == {"kind": "returns", "value": 10.12}
        and behavior["I1-negative"]
        == {"kind": "raises", "exception": "ValueError"}
    )
    c1_met = (
        apply_discount is not None
        and len(apply_discount.args.args) == 2
        and [arg.arg for arg in apply_discount.args.args]
        == ["subtotal", "percentage"]
        and new_public == expected_public
    )
    c2_met = not _external_effects(checkout)
    r1_met = "round_money" in calls
    r2_status = "UNMET"
    if inline_validation:
        r2_status = "MET"
    elif helper_used:
        r2_status = "EXCEEDED"
    r3_met = apply_discount is not None
    s1_status = "UNMET"
    if apply_discount is not None and calculation_present and (
        inline_validation or helper_used
    ):
        s1_status = "EXCEEDED" if validator_present and pricing_changed else "MET"

    statuses = {
        "O1": outcome_status,
        **behavior_status,
        "N1": (
            "MET"
            if "coupon" not in changed_source and "stacking" not in changed_source
            else "UNMET"
        ),
        "N2": (
            "MET"
            if not any(token in changed_source for token in n2_tokens)
            and _configuration_count(inventory) == 0
            else "UNMET"
        ),
        "N3": "MET" if not new_external_dependencies else "UNMET",
        "N4": derive_n4_status(base_sources, head_sources),
        "I1": "MET" if i1_met else "UNMET",
        "I2": (
            "MET"
            if behavior_status["B3"] == behavior_status["B4"] == "MET"
            else "UNMET"
        ),
        "C1": "MET" if c1_met else "UNMET",
        "C2": "MET" if c2_met else "UNMET",
        "R1": "MET" if r1_met else "UNMET",
        "R2": r2_status,
        "R3": "MET" if r3_met else "UNMET",
        "S1": s1_status,
        "S2": (
            "MET"
            if any(path == "tests/test_checkout.py" for _, path in inventory)
            and all(value == "MET" for value in acceptance.values())
            else "UNMET"
        ),
        "K-MODULES": _budget_status(
            len(new_modules),
            clauses["K-MODULES"],
        ),
        "K-DEPENDENCIES": _budget_status(
            len(new_external_dependencies),
            clauses["K-DEPENDENCIES"],
        ),
        "K-ABSTRACTIONS": _budget_status(
            len(new_abstractions),
            clauses["K-ABSTRACTIONS"],
        ),
        "K-CONFIGURATION": _budget_status(
            _configuration_count(inventory),
            clauses["K-CONFIGURATION"],
        ),
        "K-PUBLIC-INTERFACES": _budget_status(
            len(new_public),
            clauses["K-PUBLIC-INTERFACES"],
        ),
        **acceptance,
    }
    if set(statuses) != set(clauses):
        raise ValueError("not every v3 clause was derived")
    return statuses


def _axis_items(
    head_sources: Mapping[str, str],
) -> tuple[tuple[AxisItem, ...], tuple[AxisItem, ...]]:
    checkout = head_sources["src/checkout.py"]
    pricing = head_sources["src/pricing.py"]
    apply_discount = _function(ast.parse(checkout), "apply_discount")
    calls = _call_names(apply_discount)
    validator_present = "def _validate_percentage(" in pricing
    helper_used = "_validate_percentage" in calls
    inline_validation = "percentage < 0 or percentage > 100" in checkout
    wrapper_present = "_DiscountCalculation" in _class_names(checkout)

    yagni = []
    if wrapper_present:
        yagni.append(
            AxisItem(
                "Y1",
                "UNEARNED_LOCAL",
                ("ast:checkout:_DiscountCalculation",),
                "A private wrapper replaces a direct required calculation.",
            )
        )
    if validator_present and inline_validation and not helper_used:
        yagni.append(
            AxisItem(
                "Y2",
                "UNEARNED_LOCAL",
                ("ast:checkout:inline-validation", "ast:pricing:validator"),
                "Inline validation duplicates the compatible current helper.",
            )
        )

    reuse = [
        AxisItem(
            "R1",
            "REUSED" if "round_money" in calls else "BYPASSED",
            ("ast:checkout:round-money",),
            "The discount calculation's round_money use is derived from AST calls.",
        )
    ]
    if validator_present and helper_used:
        reuse.append(
            AxisItem(
                "R2",
                "REUSED",
                ("ast:checkout:validator-call",),
                "Checkout calls the compatible internal validator.",
            )
        )
    elif validator_present and inline_validation:
        reuse.append(
            AxisItem(
                "R2",
                "DUPLICATED",
                ("ast:checkout:inline-validation", "ast:pricing:validator"),
                "Checkout duplicates the compatible internal validator.",
            )
        )
    else:
        reuse.append(
            AxisItem(
                "R2",
                "NO_REUSE_AVAILABLE",
                ("git:base-and-head-search",),
                "No compatible percentage validator is available.",
            )
        )
    return tuple(yagni), tuple(reuse)


def _deviations(
    parsed_contract,
    statuses: Mapping[str, str],
) -> tuple[Deviation, ...]:
    sources = [
        clause.clause_id
        for clause in parsed_contract.clauses
        if clause_family(clause.clause_id) in {"R", "S", "K"}
        and statuses[clause.clause_id] == "EXCEEDED"
    ]
    return tuple(
        Deviation(
            deviation_id=f"U{index}",
            source_kind="derived-clause",
            source_id=source_id,
            path_id="P1",
            line=index,
            description=f"Materialized facts exceed {source_id}.",
            evidence_ids=(f"derived:{source_id}",),
            reason=f"The exact {source_id} predicate is EXCEEDED.",
        )
        for index, source_id in enumerate(sources, 1)
    )


def _parse_affected(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _probe_success(repo: Path, descriptor: dict[str, object]) -> bool:
    with tempfile.TemporaryDirectory() as temporary:
        deadline = time.monotonic() + 30
        observation = run_probe(
            probe_id="Q1",
            descriptor=descriptor,
            repository_root=repo,
            recorded_head=_git(repo, "rev-parse", "HEAD"),
            disposable_root=Path(temporary),
            git_runner=LocalGitRunner(),
            clock=time.monotonic,
            absolute_deadline=deadline,
        )
    return observation.success


def _ledger_judgment(
    repo: Path,
    statuses: Mapping[str, str],
    deviations: tuple[Deviation, ...],
    ledger_content: bytes | None,
) -> tuple[
    tuple[LedgerEntry, ...],
    tuple[DeviationMatch, ...],
    dict[str, str],
    dict[str, tuple[str, ...]],
]:
    if ledger_content is None:
        ledger_path = repo / VERSION / "execution-ledger.md"
        if not ledger_path.exists():
            return (), (), {}, {}
        ledger_content = ledger_path.read_bytes()
    parsed = parse_execution_ledger(ledger_content)
    if not parsed:
        return (), (), {}, {}

    deviation_sources = {item.source_id for item in deviations}
    ledger_entries = []
    matches = []
    statuses_by_id = {}
    affected_by_id = {}
    for entry in parsed:
        affected = _parse_affected(entry.affected_clauses)
        affected_by_id[entry.ledger_id] = affected
        helper_before = "def _validate_percentage(" in _git(
            repo,
            "show",
            "HEAD^:src/pricing.py",
        )
        implementation_after = "_validate_percentage(percentage)" in _git(
            repo,
            "show",
            "HEAD:src/checkout.py",
        )
        helper_time = _iso(_git(repo, "show", "-s", "--format=%cI", "HEAD^"))
        implementation_time = _iso(
            _git(repo, "show", "-s", "--format=%cI", "HEAD")
        )
        ledger_time = _iso(entry.timestamp)
        chronology_valid = helper_time < ledger_time < implementation_time
        probe_valid = (
            entry.probe_descriptor is not None
            and entry.probe_descriptor.get("callable") == "_validate_percentage"
            and _probe_success(repo, entry.probe_descriptor)
        )
        factual_fields_valid = (
            "_validate_percentage" in entry.discovered_fact
            and "_validate_percentage" in entry.actual_approach
            and "None" in entry.risk_delta
        )
        bounded = (
            all(
                statuses[clause_id] == "MET"
                for clause_id in statuses
                if clause_family(clause_id) in {"O", "B", "N", "I", "C", "A"}
            )
            and statuses["K-PUBLIC-INTERFACES"] == "MET"
        )
        complete = set(affected) == deviation_sources
        status = (
            "VERIFIED"
            if all(
                (
                    complete,
                    helper_before,
                    implementation_after,
                    chronology_valid,
                    probe_valid,
                    factual_fields_valid,
                    bounded,
                )
            )
            else "QUESTIONABLE"
        )
        statuses_by_id[entry.ledger_id] = status
        ledger_entries.append(LedgerEntry(entry.ledger_id, status))
        for deviation in deviations:
            if deviation.source_id in affected:
                matches.append(
                    DeviationMatch(deviation.deviation_id, entry.ledger_id)
                )
    return (
        tuple(ledger_entries),
        tuple(matches),
        statuses_by_id,
        affected_by_id,
    )


def _acceptance_qa_exists(repo: Path) -> bool:
    for path in repo.rglob("*.md"):
        if ".git" in path.parts:
            continue
        if "<!-- qa-pr-evidence -->" in path.read_text(
            encoding="utf-8",
            errors="replace",
        ):
            return True
    return False


def evaluate_materialized_fixture(
    repo: Path,
    base: str,
    rules: RulePack,
    *,
    ledger_content: bytes | None = None,
) -> SemanticEvaluation:
    repo = Path(repo).resolve()
    authority_valid = _authority_valid(repo, base)
    if not authority_valid:
        raise ValueError("semantic evaluation requires valid approved authority")

    contract_bytes = (repo / VERSION / "contract.md").read_bytes()
    parsed_contract = parse_contract(contract_bytes)
    base_sources = _sources(repo, base)
    head_sources = _sources(repo, "HEAD")
    tests_source = _git(repo, "show", "HEAD:tests/test_checkout.py")
    inventory = _inventory(repo, base)
    behavior = _behavior(repo)
    statuses = _clause_statuses(
        parsed_contract,
        base_sources,
        head_sources,
        tests_source,
        inventory,
        behavior,
    )
    clauses = tuple(
        ClauseJudgment(
            clause_id=clause.clause_id,
            status=statuses[clause.clause_id],
            evidence_ids=(f"derived:{clause.clause_id}",),
            reason=(
                f"Exact materialized facts derive {clause.clause_id} as "
                f"{statuses[clause.clause_id]}."
            ),
            contract_boundary_changed=False,
        )
        for clause in parsed_contract.clauses
    )
    yagni_items, reuse_items = _axis_items(head_sources)
    deviations = _deviations(parsed_contract, statuses)
    (
        ledger_entries,
        matches,
        ledger_statuses,
        affected_clauses,
    ) = _ledger_judgment(repo, statuses, deviations, ledger_content)
    code = CodeJudgment(
        clauses=clauses,
        path_assessments=(
            PathAssessment(
                path_id="P1",
                surface=SurfaceJudgment(
                    status=statuses["S1"],
                    evidence_ids=("derived:S1",),
                    reason="Expected surface is derived from base..HEAD paths and AST.",
                ),
                yagni_items=yagni_items,
                reuse_items=reuse_items,
            ),
        ),
        deviations=deviations,
    )
    reconciliation = ReconciliationJudgment(
        ledger_entries=ledger_entries,
        deviation_matches=matches,
        contract_obsolete=not authority_valid,
        acceptance_qa_exists=_acceptance_qa_exists(repo),
    )
    return SemanticEvaluation(
        decision=aggregate(code, reconciliation, rules),
        clause_statuses=statuses,
        deviation_sources=tuple(item.source_id for item in deviations),
        ledger_statuses=ledger_statuses,
        affected_clauses=affected_clauses,
    )


__all__ = [
    "SemanticEvaluation",
    "derive_n4_status",
    "evaluate_materialized_fixture",
]
