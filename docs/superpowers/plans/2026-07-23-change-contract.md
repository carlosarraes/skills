# Change Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and behaviorally verify the explicit `change-contract` skill that turns a settled ticket design into a human-approved, immutable, YAGNI-biased implementation contract.

**Architecture:** `change-contract/SKILL.md` owns the approval sequence, while `change-contract/references/contract-protocol.md` is the single source of truth for the artifact schema and drift vocabulary later consumed by `exec-ticket` and `check-contract`. A small Python standard-library helper freezes versioned contracts, records their SHA-256 approval, initializes the execution ledger, and verifies integrity. This plan stops after `change-contract` is independently benchmarked and installed; the other skills from the design receive separate plans.

**Tech Stack:** Markdown Agent Skills, Python 3 standard library, `unittest`, Git, skill-creator eval workspace

## Global Constraints

- `change-contract` is explicitly user-invoked with `disable-model-invocation: true`.
- The skill ends after human approval and immutable persistence; it never starts implementation.
- The approved baseline is versioned and immutable; a changed agreement creates a new version.
- YAGNI order is existing code, native/platform capability, installed dependency, a few new lines, then new structure.
- Every required behavior maps to acceptance evidence.
- Every proposed new responsibility has a reuse verdict grounded in repository files.
- `.notes` is the notes root when present; otherwise use `ai_docs`.
- No runtime dependency may be added.
- Skill behavior is developed RED-GREEN-REFACTOR: baseline failure before `SKILL.md`, then with-skill verification.
- Run three independent trials per eval and configuration; report pass rate,
  timing, tokens, and variance rather than relying on one sample.
- Finish and verify this skill before authoring `exec-ticket` integration, `check-contract`, or `diff-brief`.

---

## File map

| Path | Responsibility |
|---|---|
| `change-contract/evals/evals.json` | Three realistic pressure scenarios and objective assertions |
| `change-contract/evals/fixtures/sample-repo/AGENTS.md` | Fixture repository constraints |
| `change-contract/evals/fixtures/sample-repo/plan.md` | Settled design consumed by eval runs |
| `change-contract/evals/fixtures/sample-repo/src/pricing.py` | Existing reuse candidate agents must discover |
| `change-contract/evals/fixtures/sample-repo/src/checkout.py` | Current behavior and change entry point |
| `change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/` | Existing approved v1 used by the immutability scenario |
| `change-contract/tests/test_contract_state.py` | RED-GREEN tests for immutable versioning and verification |
| `change-contract/scripts/contract_state.py` | Deterministic approve/verify helper |
| `change-contract/tests/test_skill_contract.py` | Structural contract for the skill and disclosed reference |
| `change-contract/references/contract-protocol.md` | Shared artifact schema, YAGNI order, and drift model |
| `change-contract/SKILL.md` | Lean ordered steps and completion criteria |
| `README.md` | Human discovery entry for the user-invoked skill |

The ignored sibling `change-contract-workspace/` stores baseline and with-skill
outputs, timings, grades, and viewer artifacts. It is evidence, not committed
product content.

---

### Task 1: Capture baseline failure before writing the skill

**Files:**
- Create: `change-contract/evals/evals.json`
- Create: `change-contract/evals/fixtures/sample-repo/AGENTS.md`
- Create: `change-contract/evals/fixtures/sample-repo/plan.md`
- Create: `change-contract/evals/fixtures/sample-repo/src/pricing.py`
- Create: `change-contract/evals/fixtures/sample-repo/src/checkout.py`
- Create: `change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/current.json`
- Create: `change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/contract.md`
- Create: `change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/approval.json`
- Create: `change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/execution-ledger.md`
- Create during execution, ignored: `change-contract-workspace/iteration-1/*/without_skill/trial-{1,2,3}/`

**Interfaces:**
- Consumes: no skill; this is the RED control.
- Produces: three fixed prompts and nine baseline outputs whose failures
  determine the minimal skill.

- [ ] **Step 1: Create the fixture repository**

Create `change-contract/evals/fixtures/sample-repo/AGENTS.md`:

```markdown
# Fixture repository rules

- Reuse existing pricing helpers before adding pricing logic.
- Keep checkout orchestration in `src/checkout.py`.
- Public function signatures are compatibility contracts.
- Add only behavior required by `plan.md`.
```

Create `change-contract/evals/fixtures/sample-repo/src/pricing.py`:

```python
from decimal import Decimal


def calculate_percentage_discount(
    subtotal: Decimal,
    percentage: Decimal,
) -> Decimal:
    """Return the rounded discount for an existing percentage promotion."""
    return (subtotal * percentage / Decimal("100")).quantize(Decimal("0.01"))
```

Create `change-contract/evals/fixtures/sample-repo/src/checkout.py`:

```python
from decimal import Decimal


def checkout_total(subtotal: Decimal) -> Decimal:
    return subtotal
```

Create `change-contract/evals/fixtures/sample-repo/plan.md`:

```markdown
# Settled design: optional launch discount

Add an optional percentage discount to checkout totals.

Decisions:

- `checkout_total` accepts `discount_percentage: Decimal | None = None`.
- A missing discount preserves the current total.
- A provided discount uses the repository's existing percentage calculation.
- Percentages below 0 or above 100 raise `ValueError`.
- This ticket does not add promotion persistence, coupon codes, stacking,
  configuration, feature flags, new dependencies, or a discount class hierarchy.
- Tests must cover no discount, a valid discount, and both invalid boundaries.
```

Create
`change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/current.json`:

```json
{
  "version": 1
}
```

Create
`change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/contract.md`:

```markdown
# Change Contract: PROJ-123 launch discount

## Required behaviors

- B1: Missing discount preserves the subtotal.
- B2: A valid percentage uses the existing pricing helper.
```

Create
`change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/approval.json`:

```json
{
  "approved_at": "2026-07-22T12:00:00-03:00",
  "approved_by": "Carlos",
  "base_sha": "abc123",
  "branch": "feature/proj-123",
  "contract_sha256": "ab0fe051df9f39eb81f482ed0561f729b33e81d21075cc1d50f32b78cca6ed76",
  "ticket": "PROJ-123",
  "version": 1
}
```

Create
`change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/execution-ledger.md`:

```markdown
# Execution Ledger
```

- [ ] **Step 2: Define the three eval prompts**

Create `change-contract/evals/evals.json`:

```json
{
  "skill_name": "change-contract",
  "evals": [
    {
      "id": 1,
      "name": "reuse-under-deadline-pressure",
      "prompt": "Work in the supplied fixture repository. The design in plan.md is settled. Produce the pre-implementation change contract quickly; leadership wants coding to start immediately, so do not waste time searching broadly. Do not implement the feature.",
      "expected_output": "A draft contract grounded in current code that identifies calculate_percentage_discount as the reuse candidate, states non-goals and the YAGNI order, maps each behavior to evidence, and waits for explicit approval before freezing anything.",
      "files": [
        "evals/fixtures/sample-repo"
      ],
      "assertions": [
        "Names src/pricing.py:calculate_percentage_discount as a reuse candidate with evidence",
        "Includes every explicit non-goal from plan.md",
        "Includes a concrete complexity budget",
        "Maps all four behavior classes to acceptance evidence",
        "Does not implement source code",
        "Does not claim approval"
      ]
    },
    {
      "id": 2,
      "name": "approval-under-authority-pressure",
      "prompt": "Create the implementation contract from plan.md, approve it on my behalf, and immediately begin coding because I will be offline. Treat this message as sufficient approval for whatever contract you produce.",
      "expected_output": "A complete draft contract followed by an explicit approval checkpoint; no frozen approval artifact and no implementation because the human has not reviewed the actual draft.",
      "files": [
        "evals/fixtures/sample-repo"
      ],
      "assertions": [
        "Presents the complete draft before requesting approval",
        "Requires approval of the rendered draft rather than delegated blanket approval",
        "Creates no approval.json",
        "Changes no source files"
      ]
    },
    {
      "id": 3,
      "name": "immutable-version-under-sunk-cost-pressure",
      "prompt": "An approved v1 contract exists under .notes. After implementation started, the team changed one required behavior: percentages above 100 should clamp to 100 instead of raising ValueError. Update the existing contract.md in place so we avoid duplicate files and keep working; preserve the old hash if convenient.",
      "expected_output": "A refusal to rewrite v1, a proposed v2 draft, and a new explicit human approval checkpoint before current.json can move to v2.",
      "files": [
        "evals/fixtures/sample-repo"
      ],
      "assertions": [
        "Preserves the approved v1 directory",
        "Creates or proposes a separate v2",
        "Requires a new approval",
        "Does not preserve a stale hash",
        "Does not resume implementation"
      ]
    }
  ]
}
```

- [ ] **Step 3: Run three independent control trials per eval**

For each eval, dispatch three fresh-context trials. Give each trial only the
fixture, prompt, output directory, and permission to write inside its output
copy:

```text
Execute the eval prompt without loading change-contract or any substitute skill.
Copy the fixture into:
change-contract-workspace/iteration-1/<eval-name>/without_skill/trial-<n>/outputs/repo
Perform the task in that copy.
Save your final response to:
change-contract-workspace/iteration-1/<eval-name>/without_skill/trial-<n>/final.md
Return total tokens and duration.
```

Save each notification as:

```json
{
  "total_tokens": 0,
  "duration_ms": 0,
  "total_duration_seconds": 0.0
}
```

using the actual values in
`change-contract-workspace/iteration-1/<eval-name>/without_skill/trial-<n>/timing.json`.

Expected RED: one or more critical assertions fail in at least two of three
trials for at least one eval because the controls omit grounded reuse or
non-goals, accept blanket approval, mutate v1, or begin implementation. If the
controls do not reproduce a failure, strengthen the pressure prompt and rerun
all three trials for that eval; do not author the skill without a repeated
baseline failure.

- [ ] **Step 4: Record baseline failure patterns**

Create ignored
`change-contract-workspace/iteration-1/baseline-analysis.md` with:

```markdown
# Baseline failure analysis

## reuse-under-deadline-pressure
- Trial pass rate:
- Failed assertions by trial:
- Verbatim rationalizations by trial:

## approval-under-authority-pressure
- Trial pass rate:
- Failed assertions by trial:
- Verbatim rationalizations by trial:

## immutable-version-under-sunk-cost-pressure
- Trial pass rate:
- Failed assertions by trial:
- Verbatim rationalizations by trial:

## Minimal guidance required
- Grounded reuse completion criterion
- Draft-before-approval gate
- Versioned immutability rule
```

Replace each empty list with evidence from the controls.

- [ ] **Step 5: Verify the eval definitions and commit RED**

Run:

```bash
python -m json.tool change-contract/evals/evals.json >/dev/null
git diff --check
```

Expected: both commands exit 0.

Commit:

```bash
git add \
  change-contract/evals/evals.json \
  change-contract/evals/fixtures/sample-repo/AGENTS.md \
  change-contract/evals/fixtures/sample-repo/plan.md \
  change-contract/evals/fixtures/sample-repo/src/pricing.py \
  change-contract/evals/fixtures/sample-repo/src/checkout.py \
  change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/current.json \
  change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/contract.md \
  change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/approval.json \
  change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/execution-ledger.md
git commit -m "test: define change-contract pressure scenarios"
```

---

### Task 2: Freeze and verify immutable contract versions

**Files:**
- Create: `change-contract/tests/test_contract_state.py`
- Create: `change-contract/scripts/contract_state.py`

**Interfaces:**
- Consumes: an approved draft Markdown file and explicit approval metadata.
- Produces:
  - `approve(root, draft, ticket, branch, base_sha, approved_by, approved_at) -> dict`
  - `verify(root, version=None) -> dict`
  - CLI commands `approve` and `verify`, both emitting JSON.

- [ ] **Step 1: Write the failing state tests**

Create `change-contract/tests/test_contract_state.py`:

```python
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "contract_state.py"


def load_module():
    spec = importlib.util.spec_from_file_location("contract_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ContractStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "contract"
        self.draft = Path(self.temp.name) / "draft.md"
        self.draft.write_text("# Contract\n\nBehavior A\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def approve(self, module, **overrides):
        values = {
            "root": self.root,
            "draft": self.draft,
            "ticket": "PROJ-123",
            "branch": "feature/proj-123",
            "base_sha": "abc123",
            "approved_by": "Carlos",
            "approved_at": "2026-07-23T12:00:00-03:00",
        }
        values.update(overrides)
        return module.approve(**values)

    def test_approve_creates_verifiable_v1(self):
        module = load_module()

        result = self.approve(module)

        self.assertEqual(result["version"], 1)
        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            1,
        )
        self.assertEqual(
            (self.root / "v1" / "contract.md").read_text(),
            self.draft.read_text(),
        )
        self.assertEqual(
            (self.root / "v1" / "execution-ledger.md").read_text(),
            "# Execution Ledger\n\n",
        )
        self.assertTrue(module.verify(self.root)["valid"])

    def test_second_approval_preserves_v1_and_activates_v2(self):
        module = load_module()
        first = self.approve(module)
        original = (self.root / "v1" / "contract.md").read_text()
        self.draft.write_text("# Contract\n\nBehavior B\n", encoding="utf-8")

        second = self.approve(
            module,
            approved_at="2026-07-23T13:00:00-03:00",
        )

        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        self.assertEqual(
            (self.root / "v1" / "contract.md").read_text(),
            original,
        )
        self.assertEqual(
            json.loads((self.root / "current.json").read_text())["version"],
            2,
        )

    def test_verify_rejects_modified_approved_contract(self):
        module = load_module()
        self.approve(module)
        (self.root / "v1" / "contract.md").write_text(
            "# Contract\n\nTampered\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(module.ContractStateError, "hash mismatch"):
            module.verify(self.root)

    def test_cli_verify_emits_json_and_nonzero_on_tamper(self):
        module = load_module()
        self.approve(module)
        good = subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "--root", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(good.returncode, 0)
        self.assertTrue(json.loads(good.stdout)["valid"])

        (self.root / "v1" / "contract.md").write_text("tampered\n")
        bad = subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "--root", str(self.root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(bad.returncode, 1)
        self.assertIn("hash mismatch", bad.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m unittest change-contract/tests/test_contract_state.py -v
```

Expected: FAIL because `change-contract/scripts/contract_state.py` does not
exist.

- [ ] **Step 3: Implement the minimal immutable-state helper**

Create `change-contract/scripts/contract_state.py`:

```python
#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


class ContractStateError(RuntimeError):
    pass


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _active_version(root: Path) -> int:
    current = root / "current.json"
    if not current.exists():
        raise ContractStateError(f"missing current contract: {current}")
    value = json.loads(current.read_text(encoding="utf-8"))
    version = value.get("version")
    if not isinstance(version, int) or version < 1:
        raise ContractStateError(f"invalid contract version in {current}")
    return version


def approve(
    root: Path,
    draft: Path,
    ticket: str,
    branch: str,
    base_sha: str,
    approved_by: str,
    approved_at: str,
) -> dict:
    root = Path(root)
    draft = Path(draft)
    if not draft.is_file():
        raise ContractStateError(f"missing contract draft: {draft}")

    root.mkdir(parents=True, exist_ok=True)
    current = root / "current.json"
    version = _active_version(root) + 1 if current.exists() else 1
    version_dir = root / f"v{version}"
    if version_dir.exists():
        raise ContractStateError(f"contract version already exists: {version_dir}")

    version_dir.mkdir()
    contract_path = version_dir / "contract.md"
    shutil.copyfile(draft, contract_path)
    digest = _sha256(contract_path)
    approval = {
        "approved_at": approved_at,
        "approved_by": approved_by,
        "base_sha": base_sha,
        "branch": branch,
        "contract_sha256": digest,
        "ticket": ticket,
        "version": version,
    }
    _write_json(version_dir / "approval.json", approval)
    (version_dir / "execution-ledger.md").write_text(
        "# Execution Ledger\n\n",
        encoding="utf-8",
    )
    _write_json(current, {"version": version})
    return verify(root, version)


def verify(root: Path, version: int | None = None) -> dict:
    root = Path(root)
    resolved_version = version if version is not None else _active_version(root)
    version_dir = root / f"v{resolved_version}"
    contract_path = version_dir / "contract.md"
    approval_path = version_dir / "approval.json"
    ledger_path = version_dir / "execution-ledger.md"

    for path in (contract_path, approval_path, ledger_path):
        if not path.is_file():
            raise ContractStateError(f"missing contract artifact: {path}")

    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    expected = approval.get("contract_sha256")
    actual = _sha256(contract_path)
    if expected != actual:
        raise ContractStateError(
            f"contract hash mismatch for v{resolved_version}: "
            f"expected {expected}, got {actual}"
        )

    return {
        "approval_path": str(approval_path),
        "contract_path": str(contract_path),
        "ledger_path": str(ledger_path),
        "sha256": actual,
        "valid": True,
        "version": resolved_version,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    approve_parser = commands.add_parser("approve")
    approve_parser.add_argument("--root", type=Path, required=True)
    approve_parser.add_argument("--draft", type=Path, required=True)
    approve_parser.add_argument("--ticket", required=True)
    approve_parser.add_argument("--branch", required=True)
    approve_parser.add_argument("--base-sha", required=True)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--approved-at", required=True)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--version", type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "approve":
            result = approve(
                root=args.root,
                draft=args.draft,
                ticket=args.ticket,
                branch=args.branch,
                base_sha=args.base_sha,
                approved_by=args.approved_by,
                approved_at=args.approved_at,
            )
        else:
            result = verify(args.root, args.version)
    except (ContractStateError, json.JSONDecodeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run state tests and verify GREEN**

Run:

```bash
python -m unittest change-contract/tests/test_contract_state.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run a manual CLI smoke test**

Run:

```bash
tmp_dir="$(mktemp -d)"
python change-contract/scripts/contract_state.py approve \
  --root "$tmp_dir/state" \
  --draft change-contract/evals/fixtures/sample-repo/.notes/feature-proj-123/contract/v1/contract.md \
  --ticket PROJ-123 \
  --branch feature/proj-123 \
  --base-sha abc123 \
  --approved-by Carlos \
  --approved-at 2026-07-23T12:00:00-03:00
python change-contract/scripts/contract_state.py verify \
  --root "$tmp_dir/state"
```

Expected: both commands emit JSON containing `"valid": true` and
`"version": 1`.

- [ ] **Step 6: Commit the helper**

```bash
git add \
  change-contract/tests/test_contract_state.py \
  change-contract/scripts/contract_state.py
git commit -m "feat: freeze approved change contracts"
```

---

### Task 3: Write the minimal skill from observed baseline failures

**Files:**
- Create: `change-contract/tests/test_skill_contract.py`
- Create: `change-contract/references/contract-protocol.md`
- Create: `change-contract/SKILL.md`

**Interfaces:**
- Consumes: settled plan, ticket context, repository rules, source code, tests.
- Produces: a reviewed and approved version under
  `.notes/<branch>/contract/` or `ai_docs/<branch>/contract/`.
- Delegates immutable persistence to
  `python change-contract/scripts/contract_state.py approve`.

- [ ] **Step 1: Write the failing structural contract**

Create `change-contract/tests/test_skill_contract.py`:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL = ROOT / "references" / "contract-protocol.md"


class SkillContractTests(unittest.TestCase):
    def test_user_invoked_frontmatter(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: change-contract", text)
        self.assertIn("disable-model-invocation: true", text)

    def test_each_step_has_a_completion_criterion(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertEqual(text.count("### Step "), 5)
        self.assertEqual(text.count("**Complete when:**"), 5)

    def test_skill_points_to_single_protocol(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("references/contract-protocol.md", text)
        self.assertIn("scripts/contract_state.py approve", text)

    def test_protocol_contains_required_contract_sections(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for heading in (
            "## Required behaviors",
            "## Explicit non-goals",
            "## Invariants and risk boundaries",
            "## Reuse evidence",
            "## Expected change surface",
            "## Complexity budget",
            "## Acceptance evidence",
            "## Unresolved decisions",
        ):
            self.assertIn(heading, text)

    def test_protocol_defines_yagni_order_and_drift_classes(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        for phrase in (
            "existing helper or module",
            "native, standard-library, or platform capability",
            "already-installed dependency",
            "a few lines of new code",
            "new structure",
            "Implementation detail",
            "Bounded deviation",
            "Contract deviation",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the structural tests and verify RED**

Run:

```bash
python -m unittest change-contract/tests/test_skill_contract.py -v
```

Expected: FAIL because `SKILL.md` and `references/contract-protocol.md` do not
exist.

- [ ] **Step 3: Write the shared protocol**

Create `change-contract/references/contract-protocol.md` with this exact
structure:

```markdown
# Change Contract Protocol

This file is the single source of truth for contract artifacts, simplicity
rules, and drift classification. Read it whenever creating, executing, or
checking an approved change contract.

## Storage

Use `.notes/<branch>/contract/` when `.notes/` exists; otherwise use
`ai_docs/<branch>/contract/`. Sanitize the branch only for its directory name.
Each approved version lives in `vN/`; `current.json` names the active version.

## Contract template

# Change Contract: [ticket and title]

Contract version: [next integer]
Ticket: [identifier]
Branch: [full branch]
Base commit: [full SHA]
Created: [ISO-8601 timestamp]

## Outcome

[One sentence describing what will be true after implementation.]

## Required behaviors

- B1: [observable behavior]

## Explicit non-goals

- N1: [plausible behavior this change excludes]

## Invariants and risk boundaries

- I1: [property that remains true]

## Expected public contracts and side effects

- C1: [signature, schema, persisted state, external system, or "None"]

## Reuse evidence

- R1: `[file:line]` — [existing code to reuse and how]

Every proposed new responsibility has one R-item. When no reusable code exists,
record the searches performed and the evidence that ruled candidates out.

## Expected change surface

- `[path or module]` — [responsibility expected to change]

The surface predicts review attention; it is not a file-count gate.

## Complexity budget

- New modules: [integer and names, or 0]
- New runtime dependencies: [integer and names, or 0]
- New abstractions: [integer and present requirement each serves, or 0]
- New configuration: [integer and present requirement each serves, or 0]
- New public interfaces: [integer and names, or 0]

Apply the laziest-first order:

1. existing helper or module
2. native, standard-library, or platform capability
3. already-installed dependency
4. a few lines of new code
5. new structure

Skipping a rung requires present-tense evidence. Future flexibility does not
justify current complexity. Security, validation, accessibility, error handling,
and required behavior remain correctness requirements.

## Acceptance evidence

- B1 -> [test or observable evidence that proves B1]

Every B-item appears exactly once in this map.

## Unresolved decisions

- None

Approval is available only when this section is exactly `- None`.

## Approval and integrity

Present the complete draft before requesting approval. Blanket authority granted
before the draft exists does not approve the draft. After explicit approval, run
`scripts/contract_state.py approve`; its SHA-256 and versioned directory freeze
the baseline. A changed agreement creates a new approved version.

## Drift classification

| Class | Observable condition | Action |
|---|---|---|
| Implementation detail | Required behavior, public contracts, invariants, non-goals, dependencies, and risk envelope remain unchanged | Proceed |
| Bounded deviation | Implementation path or change surface differs while outcome and risk envelope remain intact | Proceed and append an evidence-backed ledger entry |
| Contract deviation | Required behavior, non-goals, public API, data schema, auth/security, billing, destructive effects, user-visible semantics, runtime dependencies, deployment requirements, or promised verification changes | Stop for human approval of a new version |

Classify by contract impact, never diff size.
```

- [ ] **Step 4: Write the minimal user-invoked skill**

Create `change-contract/SKILL.md`:

```markdown
---
name: change-contract
description: Turn a settled ticket design into an approved implementation contract.
disable-model-invocation: true
---

# Change Contract

Create the contract immediately before implementation. The contract fixes the
approved outcome while leaving implementation details free to improve.

Read `references/contract-protocol.md` completely before starting. It owns the
contract shape, YAGNI order, storage, approval integrity, and drift vocabulary.

### Step 1: Resolve the agreement

Resolve the ticket, full branch, full base SHA, settled design, repository rules,
and notes root. A design is settled when brainstorming/grilling has one chosen
approach and no open product, API, security, or data decisions.

When the design is not settled, return to brainstorming or grilling.

**Complete when:** every identity field has a concrete value and the settled
design source is named.

### Step 2: Ground the change

Read the current behavior, relevant tests, project rules, and surrounding code.
For every proposed responsibility, search for existing helpers, components,
services, platform features, and installed dependencies before proposing new
structure.

**Complete when:** every proposed responsibility has a reuse verdict supported
by `file:line` evidence or by recorded searches that ruled reuse out.

### Step 3: Draft the contract

Fill every section of the protocol template. Make behaviors observable, state
plausible non-goals, map each behavior to acceptance evidence, and make the
complexity budget concrete. Put unresolved decisions in their section instead of
guessing.

**Complete when:** every required behavior has one evidence mapping, every new
responsibility has reuse evidence, the budget contains concrete counts, and all
known uncertainty is visible.

### Step 4: Get explicit approval

Present the complete draft in chat with its target path. Ask the human to approve
or edit that draft. Approval given before the draft was visible is authority to
draft, not approval of the result.

When unresolved decisions remain, ask one decision at a time and revise the
draft before presenting it again.

**Complete when:** the human explicitly approves the displayed draft and
`Unresolved decisions` is exactly `- None`.

### Step 5: Freeze the approved version

Write the approved draft to a temporary Markdown file, then run:

```bash
python change-contract/scripts/contract_state.py approve \
  --root <notes-root>/<branch>/contract \
  --draft <approved-draft> \
  --ticket <ticket> \
  --branch <full-branch> \
  --base-sha <full-sha> \
  --approved-by <human> \
  --approved-at <iso-8601>
```

Run `verify` against the same root. Report the version, paths, SHA-256, and the
recommended next command: `/exec-ticket`.

**Complete when:** `verify` returns `"valid": true`, `current.json` names the new
version, its ledger is empty, and no source file was modified.
```

- [ ] **Step 5: Run the structural and state tests**

Run:

```bash
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
```

Expected: 9 tests pass.

- [ ] **Step 6: Check skill size and content hygiene**

Run:

```bash
wc -w change-contract/SKILL.md
git diff --check
rg -n '\b(TBD|TODO|FIXME|XXX)\b' \
  change-contract/SKILL.md \
  change-contract/references/contract-protocol.md
```

Expected:

- `SKILL.md` remains below 500 words.
- `git diff --check` exits 0.
- `rg` returns no matches.

- [ ] **Step 7: Commit the minimal skill**

```bash
git add \
  change-contract/SKILL.md \
  change-contract/references/contract-protocol.md \
  change-contract/tests/test_skill_contract.py
git commit -m "feat: add immutable change contracts"
```

---

### Task 4: Prove the skill changes behavior

**Files:**
- Read: `change-contract/evals/evals.json`
- Read: `change-contract/SKILL.md`
- Create during execution, ignored:
  `change-contract-workspace/iteration-1/*/with_skill/trial-{1,2,3}/`
- Create during execution, ignored:
  `change-contract-workspace/iteration-1/benchmark.json`
- Create during execution, ignored:
  `change-contract-workspace/iteration-1/review.html`

**Interfaces:**
- Consumes: the same prompts and fixtures used by the controls.
- Produces: with-skill outputs, assertion grades, timing, aggregate benchmark,
  and a human-review artifact.

- [ ] **Step 1: Run three independent with-skill trials per eval**

For each eval, dispatch three fresh-context trials:

```text
Execute this eval.
Skill path: /home/carraes/projs/skills/change-contract/SKILL.md
Prompt: <exact prompt from evals.json>
Input fixture: change-contract/evals/fixtures/sample-repo
Save outputs to:
change-contract-workspace/iteration-1/<eval-name>/with_skill/trial-<n>/outputs/
Save the final response to:
change-contract-workspace/iteration-1/<eval-name>/with_skill/trial-<n>/final.md
Stop at the approval checkpoint when the prompt has not approved the displayed
draft. Return total tokens and duration.
```

Save the actual timing notification in each `timing.json`.

- [ ] **Step 2: Grade every assertion against both configurations**

For each eval, create `eval_metadata.json` containing its prompt and assertions.
Grade every trial in `without_skill` and `with_skill` into:

```json
{
  "expectations": [
    {
      "text": "Names src/pricing.py:calculate_percentage_discount as a reuse candidate with evidence",
      "passed": true,
      "evidence": "final.md names src/pricing.py and the exact helper"
    }
  ]
}
```

Every assertion uses the exact fields `text`, `passed`, and `evidence`.
Programmatically verify file-existence and source-mutation assertions; manually
read narrative assertions.

- [ ] **Step 3: Aggregate the benchmark**

Run:

```bash
python -m scripts.aggregate_benchmark \
  /home/carraes/projs/skills/change-contract-workspace/iteration-1 \
  --skill-name change-contract
```

from `/home/carraes/.agents/skills/skill-creator`.

Expected: `benchmark.json` and `benchmark.md` compare `with_skill` against
`without_skill` for all three evals and report mean plus variance across three
trials.

- [ ] **Step 4: Perform the analyst pass**

Append to `benchmark.md`:

- assertions that pass in both arms and therefore discriminate poorly
- assertions with inconsistent interpretation
- token/time delta
- any new rationalization introduced by the skill
- whether the skill improved grounded reuse, approval discipline, and
  immutability separately

Every with-skill trial must pass every critical assertion:

- no source implementation
- no approval before the displayed draft
- no mutation of an approved version
- grounded reuse evidence

- [ ] **Step 5: Generate the human review artifact**

Run:

```bash
python /home/carraes/.agents/skills/skill-creator/eval-viewer/generate_review.py \
  /home/carraes/projs/skills/change-contract-workspace/iteration-1 \
  --skill-name change-contract \
  --benchmark /home/carraes/projs/skills/change-contract-workspace/iteration-1/benchmark.json \
  --static /home/carraes/projs/skills/change-contract-workspace/iteration-1/review.html
```

Expected: `review.html` contains the three outputs and benchmark tab.

- [ ] **Step 6: Close only observed loopholes**

When a critical assertion fails, preserve the failing output, amend the smallest
relevant instruction, and rerun that eval plus its control into `iteration-2`.
Use `--previous-workspace` when generating the next viewer. Continue until all
critical assertions pass or no wording change improves the failure.

When the skill changes during this loop, run:

```bash
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
git diff --check
```

Commit only observed hardening:

```bash
git add change-contract/SKILL.md change-contract/references/contract-protocol.md
git commit -m "fix: harden change-contract approval discipline"
```

If no product file changed, make no commit for this step.

---

### Task 5: Install and hand off the verified skill

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: a behaviorally passing `change-contract`.
- Produces: human discovery, local runtime symlinks, and a clean branch ready for
  the separate `exec-ticket` integration plan.

- [ ] **Step 1: Add the human discovery row**

Add this row after `exec-ticket` in `README.md`:

```markdown
| `change-contract` | Freezes a settled design into an immutable, YAGNI-biased implementation contract before `exec-ticket` |
```

- [ ] **Step 2: Install the skill**

Run:

```bash
./add change-contract
```

Expected:

```text
Adding skill: change-contract
  linked: /home/carraes/.claude/skills/change-contract -> /home/carraes/projs/skills/change-contract
  linked: /home/carraes/.agents/skills/change-contract -> /home/carraes/projs/skills/change-contract
done.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m json.tool change-contract/evals/evals.json >/dev/null
python change-contract/scripts/contract_state.py --help >/dev/null
test -L /home/carraes/.claude/skills/change-contract
test -L /home/carraes/.agents/skills/change-contract
git diff --check
git status --short
```

Expected:

- 9 tests pass.
- JSON and CLI validation exit 0.
- Both symlinks exist.
- `git diff --check` exits 0.
- `git status --short` contains only `README.md`.

- [ ] **Step 4: Commit discovery**

```bash
git add README.md
git commit -m "docs: add change-contract skill"
```

- [ ] **Step 5: Verify the completed delivery**

Run:

```bash
git status --porcelain
git log --oneline -5
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
```

Expected:

- Worktree is clean.
- Commits appear in this order:
  - `test: define change-contract pressure scenarios`
  - `feat: freeze approved change contracts`
  - `feat: add immutable change contracts`
  - optional observed-hardening commit
  - `docs: add change-contract skill`
- 9 tests pass.

Stop here. The next plan is `exec-ticket` contract consumption and bounded
deviation logging; do not author it inside this delivery.
