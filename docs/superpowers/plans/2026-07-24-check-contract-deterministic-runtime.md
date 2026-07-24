# Check Contract Deterministic Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development to implement this plan task-by-task.
> Every task uses a fresh implementer, a generated review package, and an
> independent task review. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the prompt-only `/check-contract` procedure with a
provider-neutral continuation runtime that structurally enforces immutable
authority, code-first evidence, deterministic verdicts/routes, report-only
publication, and strict A-then-B closure, then pass all 9 behavioral treatment
samples.

**Architecture:** A deep `AuditRuntime.advance(StartAudit | ContinueAudit)`
module owns the full workflow and returns only `NeedJudgment`,
`AuditComplete`, or `AuditStopped`. The current agent remains the semantic
classifier through two closed-schema continuation responses: code judgment
before any narrative is exposed, then reconciliation judgment after guarded
ledger/narrative disclosure. A thin CLI exposes `start` plus repeated
`continue`; a pure JSON policy pack owns enums, aggregation, precedence, and
routes.

**Tech Stack:** Python 3 standard library, Git object plumbing, JSON Schema-like
closed validation implemented locally, `unittest`, Markdown Agent Skills,
Claude Code isolated behavioral evals, skill-creator benchmark viewer

## Global Constraints

- The approved contract, approval, pointer, and execution ledger remain
  read-only. A changed agreement requires a new human-approved version.
- The only permitted target-repository mutation is atomic creation or
  replacement of the active version's `check-report.md`.
- `/check-contract` remains explicit-only with
  `disable-model-invocation: true`.
- The audit is code-first: the runtime freezes code evidence and accepts the
  code judgment before reading or exposing ledger, summary, PR, or prior-report
  narrative content.
- The runtime never fixes, commits, pushes, posts, approves, resolves threads,
  or invokes a recommended skill.
- The runtime owns authority resolution, immutable guards, Git range and
  evidence capture, phase transitions, evidence IDs, schema validation,
  stable IDs, aggregation, routing, replay isolation, freshness, rendering,
  atomic publication, and mutation attestation.
- The model may supply only closed-schema semantic judgments that cite
  runtime-issued evidence IDs. It cannot choose aggregate axes, verdict,
  route, report path, deadline, phase, or mutation.
- Fidelity-owned clauses may cite only behavior, public-contract, risk, and
  acceptance evidence namespaces. Surface, complexity, and reuse evidence
  cannot make Outcome/B/N/I/C fail.
- Every changed path receives an explicit simplicity/reuse assessment; missing
  coverage becomes indeterminate and can never aggregate to YAGNI/Reuse PASS.
- A phase transition is monotonic. Each response is accepted at most once.
  Invalid, stale, duplicate, expired, or out-of-phase responses hard-stop with
  no retry and no report replacement.
- Session state lives outside every target repository, is content-addressed,
  read-only between calls, and is revalidated on every continuation.
- The absolute deadline is fixed at start, is at most 300 seconds, includes
  agent pauses, preserves a finalization reserve, and cannot be extended.
- Evidence collection uses the approved base and recorded full HEAD Git
  objects. It never imports or runs target implementation code.
- A reconciliation response may select at most one runtime-issued,
  ledger-stated replay probe. The runtime executes the exact captured argv
  once, without a shell, from `git archive <recorded-head>` in a disposable
  directory outside the target, with bytecode disabled and a bounded timeout.
- Compound A-then-B uses one runtime session. A reaches `Closed` before B is
  touched; once B begins, only an opaque A closure digest remains and no later
  runtime action resolves, reads, or names A.
- No provider SDK, nested-agent integration, generic adapter ecosystem, or
  general semantic fact graph is added in this version.
- Preserve iteration-1 through iteration-3 artifacts exactly. New trials go in
  a new immutable iteration directory and are never retried or overwritten.
- Behavioral acceptance remains exact: 9/9 treatment samples must pass every
  critical assertion. Improved partial assertion coverage is not acceptance.
- Fix the independent causal review's two eval-model caveats before the next
  run: AB1 is compound-only, and report delivery is separate from mutation
  scope.
- Use RED-GREEN-REFACTOR for every product change and make focused conventional
  commits.

---

## File Map

| Path | Responsibility |
|---|---|
| `change-contract/references/contract-check-rules.json` | Executable enums, namespace ownership, aggregation, precedence, routes, and report schema version |
| `change-contract/references/contract-protocol.md` | Human semantics and link to the executable rule pack |
| `check-contract/scripts/audit_domain.py` | Frozen policy/domain types and strict v1 rule-pack loading |
| `check-contract/scripts/audit_validation.py` | Closed response parsing, namespace enforcement, and derived deviation coverage |
| `check-contract/scripts/audit_policy.py` | Pure aggregation, precedence, stable findings, and conditional routes |
| `check-contract/scripts/audit_runtime.py` | Deep public continuation facade and target-phase orchestration |
| `check-contract/scripts/audit_session.py` | Append-only immutable generations, manifests, tokens, nonces, and atomic claims |
| `check-contract/scripts/audit_evidence.py` | Strict contract parser and bounded recorded-HEAD evidence capture |
| `check-contract/scripts/audit_reconciliation.py` | Strict ledger/narrative parsing and issued probe descriptors |
| `check-contract/scripts/probe_runner.py` | Fixed no-shell `python-call-v1` replay executor |
| `check-contract/scripts/audit_report.py` | Deterministic report rendering, freshness checks, atomic publication, mutation attestation |
| `check-contract/scripts/check_contract.py` | Thin `start`/`continue` JSON CLI |
| `check-contract/tests/runtime_fixtures.py` | Temporary-repository and response builders used only by runtime tests |
| `check-contract/tests/test_audit_policy.py` | Pure rule/aggregation and evidence-namespace regressions |
| `check-contract/tests/test_audit_runtime.py` | Authority, phase, deadline, freshness, publication, probe, and compound invariants |
| `check-contract/tests/test_check_contract_cli.py` | Three-call CLI envelope and failure exit behavior |
| `check-contract/tests/test_skill_contract.py` | Thin-skill choreography and portability contract |
| `check-contract/evals/assertion_contract.py` | Correct A/B/compound slices and separated delivery/mutation assertions |
| `check-contract/evals/evals.json` | Updated objective assertion wording/order for the next immutable run |
| `check-contract/tests/test_eval_contract.py` | Eval-model regression tests |
| `check-contract/SKILL.md` | Compact agent choreography around runtime packets only |
| `check-contract/evals/README.md` | Runtime snapshot and immutable-trial policy |
| `README.md` | Discovery after behavioral acceptance |

Ignored runtime/eval evidence:

```text
check-contract-workspace/iteration-4/**
.superpowers/sdd/check-contract-runtime-*.md
```

---

### Task 1: Correct the evaluation contract without rewriting history

**Files:**

- Modify: `check-contract/evals/assertion_contract.py`
- Modify: `check-contract/evals/evals.json`
- Modify: `check-contract/tests/test_eval_contract.py`
- Modify: `check-contract/evals/README.md`

**Interfaces:**

- Consumes: the frozen iteration-3 assertion order and independent causal
  review at `.superpowers/sdd/task-4-iteration3-causal-review.md`
- Produces:
  `split_compound_outcomes(expectations: list[bool]) -> dict[str, bool]`
  with disjoint A, B, and compound-only AB1 ownership; a separate
  `report_delivered` assertion and `mutation_scope_preserved` assertion

- [ ] **Step 1: Write failing outcome-slice regressions**

Add tests that prove AB1 cannot contaminate `target_b_pass`:

```python
def test_compound_outcomes_keep_boundary_out_of_target_b(self):
    outcomes = ASSERTIONS.split_compound_outcomes(
        [True, True, True, True, False] + [True] * 14
    )
    self.assertTrue(outcomes["target_a_pass"])
    self.assertTrue(outcomes["target_b_pass"])
    self.assertFalse(outcomes["compound_pass"])
```

Add a shape test that requires two distinct common assertions:

```python
def test_delivery_and_mutation_scope_are_distinct_assertions(self):
    document = json.loads(EVALS.read_text(encoding="utf-8"))
    for item in document["evals"]:
        assertions = item["assertions"]
        self.assertTrue(
            any(
                "active contract version's check-report.md is delivered"
                in value
                for value in assertions
            )
        )
        self.assertTrue(
            any(
                "target path changes except the active contract "
                "version's check-report.md" in value
                for value in assertions
            )
        )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```text
python -m unittest \
  check-contract.tests.test_eval_contract.EvalContractTests.test_compound_outcomes_keep_boundary_out_of_target_b \
  check-contract.tests.test_eval_contract.EvalContractTests.test_delivery_and_mutation_scope_are_distinct_assertions \
  -v
```

Expected: FAIL because the splitter and distinct assertions do not exist.

- [ ] **Step 3: Implement the disjoint outcome splitter**

Define the canonical slices once:

```python
A_SLICE = slice(0, 4)
AB_SLICE = slice(4, 5)
B_SLICE = slice(5, 20)


def split_compound_outcomes(expectations):
    if len(expectations) != 20:
        raise ValueError("compound expectation count must be 20")
    target_a = all(expectations[A_SLICE])
    boundary = all(expectations[AB_SLICE])
    target_b = all(expectations[B_SLICE])
    return {
        "target_a_pass": target_a,
        "target_b_pass": target_b,
        "compound_pass": target_a and boundary and target_b,
    }
```

Replace the ambiguous common C7 wording with two assertions, preserving
scenario-specific meaning:

```text
The active contract version's check-report.md is delivered.
No target path changes except the active contract version's check-report.md.
```

Update assertion counts/order in `evals.json` and the canonical assertion map;
do not edit any preserved grading file or old benchmark.

- [ ] **Step 4: Document versioned assertion semantics**

Add to `evals/README.md`:

```markdown
Iteration 4 uses assertion contract v2. AB1 is compound-only: it contributes
to `compound_pass`, never `target_b_pass`. Report delivery and mutation scope
are distinct assertions. Iterations 1-3 retain their original assertions and
grades and must not be rewritten.
```

- [ ] **Step 5: Run all eval-contract tests**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_eval_contract.py' -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```text
git add check-contract/evals check-contract/tests/test_eval_contract.py
git commit -m "test: clarify check-contract behavioral outcomes"
```

---

### Task 2: Create the executable policy pack and pure aggregation kernel

**Files:**

- Create: `change-contract/references/contract-check-rules.json`
- Create: `check-contract/scripts/audit_runtime.py`
- Create: `check-contract/scripts/audit_domain.py`
- Create: `check-contract/scripts/audit_validation.py`
- Create: `check-contract/scripts/audit_policy.py`
- Create: `check-contract/tests/test_audit_policy.py`
- Modify: `change-contract/references/contract-protocol.md`

**Interfaces:**

- Consumes: clause, ledger, axis, verdict, and routing semantics currently in
  `contract-protocol.md`
- Produces:
  `load_rules(path: Path) -> RulePack`,
  `validate_code_judgment(packet, response) -> CodeJudgment`,
  `aggregate(code, reconciliation, rules) -> AuditDecision`

- [ ] **Step 1: Write failing policy tests for the observed semantic defects**

Create table-driven tests for:

```python
CASES = (
    {
        "name": "surface-and-private-class-do-not-fail-fidelity",
        "owned": {"O1": "MET", "B1": "MET", "I1": "MET", "C1": "MET",
                  "A-B1": "MET"},
        "surface": "EXCEEDED",
        "yagni_items": ["UNEARNED_LOCAL"],
        "reuse_items": ["DUPLICATED"],
        "expected": ("PASS", "WARNING", "FAIL",
                     "NEEDS HUMAN REVIEW", ["clean-up"]),
    },
    {
        "name": "required-validation-is-not-bloat",
        "owned": {"O1": "MET", "B1": "UNMET", "I1": "MET", "C1": "MET",
                  "A-B1": "INDETERMINATE"},
        "surface": "MET",
        "yagni_items": [],
        "reuse_items": ["REUSED"],
        "expected": ("FAIL", "PASS", "PASS",
                     "CONTRACT VIOLATED", ["exec-ticket"]),
    },
)
```

Also assert:

```python
def test_fidelity_rejects_simplicity_evidence_namespace(self):
    response = valid_code_response()
    response["clauses"]["O1"]["evidence_ids"] = ["complexity:K1"]
    with self.assertRaisesRegex(AuditInputError, "evidence namespace"):
        validate_code_judgment(self.packet, response)
```

- [ ] **Step 2: Run the policy tests and verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_policy.py' -v
```

Expected: FAIL because the rule pack and policy kernel do not exist.

- [ ] **Step 3: Add the canonical JSON rule pack**

The JSON must contain only executable policy data:

```json
{
  "schema_version": 1,
  "statuses": {
    "clause": ["MET", "UNMET", "EXCEEDED", "INDETERMINATE"],
    "ledger": ["VERIFIED", "QUESTIONABLE", "CONTRADICTED"],
    "fidelity": ["PASS", "PARTIAL", "FAIL"],
    "yagni": ["PASS", "WARNING", "FAIL"],
    "reuse": ["PASS", "WARNING", "FAIL"],
    "documented_drift": ["NONE", "ACCEPTED", "QUESTIONABLE"],
    "undocumented_drift": ["NONE", "PRESENT"]
  },
  "fidelity_families": ["O", "B", "N", "I", "C", "A"],
  "fidelity_evidence_namespaces": [
    "behavior", "public-contract", "risk", "acceptance"
  ],
  "precedence": [
    "CONTRACT_OBSOLETE",
    "FIDELITY_FAIL_WITH_SIMPLICITY",
    "FIDELITY_FAIL",
    "UNRESOLVED_WITH_SIMPLICITY",
    "UNRESOLVED",
    "SIMPLICITY_ONLY",
    "PASS_WITH_DOCUMENTED_DRIFT",
    "PASS"
  ],
  "routes": {
    "CONTRACT_OBSOLETE": ["change-contract"],
    "FIDELITY_FAIL_WITH_SIMPLICITY": ["exec-ticket", "clean-up"],
    "FIDELITY_FAIL": ["exec-ticket"],
    "UNRESOLVED_WITH_SIMPLICITY": ["clean-up"],
    "UNRESOLVED": ["qa-ticket"],
    "SIMPLICITY_ONLY": ["clean-up"],
    "PASS_WITH_DOCUMENTED_DRIFT": {
      "acceptance_qa_exists": ["qa-pr"],
      "otherwise": ["qa-ticket"]
    },
    "PASS": {
      "acceptance_qa_exists": ["qa-pr"],
      "otherwise": ["qa-ticket"]
    }
  },
  "report_schema_version": 1
}
```

- [ ] **Step 4: Implement immutable domain types and pure aggregation**

Add frozen dataclasses and closed validation:

```python
@dataclass(frozen=True)
class AuditDecision:
    fidelity: str
    yagni: str
    reuse: str
    documented_drift: str
    undocumented_drift: str
    verdict: str
    route: tuple[str, ...]
    findings: tuple[Finding, ...]

    @property
    def finding_ids(self) -> tuple[str, ...]:
        return tuple(item.finding_id for item in self.findings)


def aggregate(code, reconciliation, rules):
    fidelity = _aggregate_fidelity(code.clauses, rules)
    yagni = _aggregate_yagni(code.path_assessments)
    reuse = _aggregate_reuse(code.path_assessments)
    documented = _aggregate_documented(reconciliation.ledger_entries)
    undocumented = _aggregate_undocumented(
        code.deviations, reconciliation.deviation_matches
    )
    return _apply_precedence(
        fidelity, yagni, reuse, documented, undocumented,
        reconciliation.contract_obsolete, rules
    )
```

The validator and policy kernel must require:

- exactly the runtime-issued clause IDs and changed-path IDs;
- only closed enum values;
- only issued evidence IDs;
- fidelity namespace ownership;
- non-empty reason text;
- no aggregate, verdict, route, report-path, or mutation fields; and
- no extra JSON keys.

They also derive `U*` deviations from every non-`MET` expected-surface,
complexity-budget, and changed-path surface fact so response omission cannot
produce a false PASS. Findings retain source identity/path/line/reason, sort by
protocol order, and receive `F*` only after sorting.

- [ ] **Step 5: Split focused policy responsibilities behind the facade**

Keep `audit_runtime.py` as the public re-export seam. Put frozen domain/rule
loading in `audit_domain.py`, response parsing in `audit_validation.py`, and
pure aggregation/finding construction in `audit_policy.py`. Do not duplicate
validation helpers or introduce runtime/provider behavior.

- [ ] **Step 6: Make the protocol point to executable truth**

Keep the human-readable vocabulary and precedence explanation in
`contract-protocol.md` so existing consumers remain green, and add:

```markdown
`contract-check-rules.json` is the executable source of truth for closed
enums, evidence-namespace ownership, aggregation order, route precedence, and
report schema version. This section explains those rules; consumers must load
and validate the JSON rather than scraping Markdown.
```

- [ ] **Step 7: Run policy and existing protocol suites**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_audit_policy.py' -v
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```text
git add change-contract/references/contract-check-rules.json \
  change-contract/references/contract-protocol.md \
  check-contract/scripts/audit_domain.py \
  check-contract/scripts/audit_validation.py \
  check-contract/scripts/audit_policy.py \
  check-contract/scripts/audit_runtime.py \
  check-contract/tests/test_audit_policy.py
git commit -m "feat: add deterministic contract audit policy"
```

---

### Task 3: Declare one closed, replayable ledger probe

**Files:**

- Modify: `change-contract/references/contract-protocol.md`
- Modify:
  `check-contract/evals/fixtures/documented-drift/overlay/.notes/feature-proj-123/contract/v1/execution-ledger.md`
- Modify: `check-contract/evals/fixture-manifest.json`
- Modify: `check-contract/tests/test_eval_contract.py`

**Interfaces:**

- Consumes: the existing optional D-entry body
- Produces: optional exact field
  `Replay probe: <canonical JSON python-call-v1 descriptor>`

- [ ] **Step 1: Write failing closed-probe fixture tests**

Require D1 to contain exactly:

```json
{
  "kind": "python-call-v1",
  "module": "src.pricing",
  "callable": "validate_percentage",
  "cases": [
    {"args": [0], "expect": "returns"},
    {"args": [100], "expect": "returns"},
    {"args": [-1], "expect": "raises", "exception": "ValueError"},
    {"args": [101], "expect": "raises", "exception": "ValueError"}
  ]
}
```

Add a regression that rejects an unknown kind, extra keys, shell/argv fields,
non-identifier module/callable names, non-list args, unsupported exceptions,
and a case containing both/none of the required expectation shapes.

- [ ] **Step 2: Run the focused eval-contract tests and verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_eval_contract.py' -v
```

Expected: FAIL because D1 has no closed replay declaration.

- [ ] **Step 3: Define the optional protocol field and update D1**

Document `python-call-v1` as data, never command text:

```markdown
- Replay probe: `{"kind":"python-call-v1",...}`
```

Only dotted Python identifiers, positional JSON-scalar args,
`expect: returns`, and `expect: raises` with the built-in exception
`ValueError` are supported in v1. Unknown kinds/fields hard-stop. The runtime,
not the ledger or model, owns the no-shell probe runner.

Keep the human evidence sentence and add the canonical compact JSON field to
D1. Do not modify any preserved iteration-1 through iteration-3 repository.

- [ ] **Step 4: Recompute only the canonical future fixture HEAD**

Use the canonical materializer and fixed Git metadata. Update only the
documented-drift expected HEAD in `fixture-manifest.json`; the changed-path
inventory remains identical. Prove a fresh materialization is clean and its
authority/base bytes are otherwise unchanged.

- [ ] **Step 5: Run eval and shared suites**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```text
git add change-contract/references/contract-protocol.md \
  check-contract/evals/fixtures/documented-drift \
  check-contract/evals/fixture-manifest.json \
  check-contract/tests/test_eval_contract.py
git commit -m "feat: declare closed contract replay probes"
```

---

### Task 4: Build the code phase and immutable session generations

**Files:**

- Modify: `check-contract/scripts/audit_runtime.py`
- Create: `check-contract/scripts/audit_session.py`
- Create: `check-contract/scripts/audit_evidence.py`
- Create: `check-contract/tests/runtime_fixtures.py`
- Create: `check-contract/tests/test_audit_runtime_start.py`

**Interfaces:**

```python
AuditRuntime.advance(
    StartAudit | ContinueAudit
) -> NeedJudgment | AuditComplete | AuditStopped
```

Task 4 implements `StartAudit` for a single target. Later tasks implement the
continuations and compound transition without changing these envelopes.

- [ ] **Step 1: Build canonical test fixtures**

Expose:

```python
def materialized_repo(
    scenario: str, target: str = "target"
) -> ContextManager[Path]:
    ...


def packet_of(result: NeedJudgment) -> dict:
    return json.loads(result.packet_path.read_text(encoding="utf-8"))
```

Fixtures call the canonical materializer and never duplicate contract state.

- [ ] **Step 2: Write failing start/session tests**

Cover:

- shared two-root authority and exact base/HEAD;
- malformed contract sections/IDs hard-stop before evidence;
- exact clause IDs O/B/N/I/C/R/S/K/A;
- code packet contains no ledger, summary, PR, or prior-report bytes;
- one name inventory, one recorded-HEAD source/test capture, and one
  deterministic full-HEAD reuse search;
- dirty worktree disclosure without treating worktree source as authority;
- deadline maximum 300 seconds and immutable absolute deadline;
- session directory outside target with mode `0700`;
- generation files read-only and content-addressed;
- wrong digest/manifest rejected; and
- authority failure preserves an existing report and writes nothing.

- [ ] **Step 3: Verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_start.py' -v
```

Expected: FAIL because start/session/evidence behavior does not exist.

- [ ] **Step 4: Implement frozen public envelopes**

Use frozen dataclasses:

```python
@dataclass(frozen=True)
class AuditTarget:
    repo: Path
    branch: str
    ticket: str
    narrative_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class StartAudit:
    primary: AuditTarget
    then: AuditTarget | None = None
    deadline_seconds: int = 300


@dataclass(frozen=True)
class ContinueAudit:
    session: str
    response_path: Path


@dataclass(frozen=True)
class NeedJudgment:
    session: str
    target: str
    kind: str
    packet_path: Path
    packet_sha256: str
    response_path: Path
    next_command: tuple[str, ...]
    nonce: str
    a_closure_digest: str | None = None
    closed_target: Mapping[str, object] | None = None


@dataclass(frozen=True)
class AuditComplete:
    verdict: str
    route: tuple[str, ...]
    report_path: Path
    report_sha256: str
    mutation_attestation: Mapping[str, object]


@dataclass(frozen=True)
class AuditStopped:
    code: str
    reason: str
    target: str
    prior_report_preserved: bool
    zero_target_writes: bool
```

- [ ] **Step 5: Implement append-only immutable generations**

`audit_session.py` owns:

1. a random run directory outside targets, mode `0700`;
2. canonical `state.json` plus `manifest.json` under a directory named by the
   state SHA-256;
3. read-only generation files before returning;
4. an opaque token carrying only random run ID and generation digest;
5. atomic one-use claim via `mkdir(claims/<generation-digest>)`; and
6. appending a new immutable generation or terminal tombstone without
   modifying an old generation.

Every `NeedJudgment` has a new session token. The exact `response_path` is an
absent inbox file outside every target.

- [ ] **Step 6: Implement strict contract parsing and code evidence**

Parse the verified approved contract before evidence capture; it is immutable
authority, not author narrative. Issue O/B/N/I/C/R/S/K/A IDs and hard-stop
missing/duplicate/malformed fixed sections.

Derive one sorted literal reuse query from:

- identifiers in changed implementation hunks;
- identifiers in Outcome/B/C/R/expected-surface contract text; and
- changed public symbol names.

Drop a fixed checked-in stopword set and tokens shorter than three characters.
Run one no-shell `git grep -n -I` against recorded full HEAD/full tree. Store
query, scope, results, and truncation under typed evidence IDs. Truncation
makes uncovered reuse indeterminate and cannot yield Reuse PASS.

Return `NeedJudgment(kind="code")`; do not implement `continue` yet.

- [ ] **Step 7: Run focused and shared suites**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_start.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_policy.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```text
git add check-contract/scripts/audit_runtime.py \
  check-contract/scripts/audit_session.py \
  check-contract/scripts/audit_evidence.py \
  check-contract/tests/runtime_fixtures.py \
  check-contract/tests/test_audit_runtime_start.py
git commit -m "feat: freeze contract code evidence sessions"
```

---

### Task 5: Add the code-to-reconciliation continuation

**Files:**

- Modify: `check-contract/scripts/audit_runtime.py`
- Create: `check-contract/scripts/audit_reconciliation.py`
- Create: `check-contract/tests/test_audit_runtime_reconciliation.py`

**Interfaces:**

Both response kinds use this exact envelope:

```json
{
  "schema_version": 1,
  "session": "<issued generation token>",
  "nonce": "<issued one-use nonce>",
  "packet_sha256": "<issued packet digest>",
  "kind": "code",
  "judgment": {}
}
```

The second kind is `reconciliation`. Extra/missing keys hard-stop.

- [ ] **Step 1: Write failing one-use/code-first tests**

Cover invalid, extra-key, missing-key, wrong-session, wrong-kind,
wrong-packet, wrong-nonce, duplicate, stale, out-of-phase, and expired
responses. Each consumes the generation once and returns `AuditStopped`
without a retry or report write.

Prove no narrative bytes are read before a fully valid code envelope and
Task 2 inner judgment. After acceptance, prove ledger, active prior report,
explicit `narrative_paths`, and implementation-summary paths deferred from the
name inventory are read from guarded sources.

- [ ] **Step 2: Write failing ledger/reconciliation packet tests**

Require:

- strict D IDs/order and complete required D fields;
- exact parsing of optional `python-call-v1`;
- opaque issued probe IDs, never argv/code from the model;
- exact code deviation IDs available for matching;
- runtime-derived `acceptance_qa_exists`, not a model field;
- `contract_obsolete` and every ledger status cite issued evidence IDs; and
- the reconciliation packet contains guarded narrative only now.

- [ ] **Step 3: Verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_reconciliation.py' -v
```

Expected: FAIL because `continue` and reconciliation parsing do not exist.

- [ ] **Step 4: Implement claim-before-validation and strict envelopes**

On `ContinueAudit`, verify immutable generation/manifest, atomically claim it,
then validate the exact response path and envelope. Any error appends a
terminal tombstone and returns `AuditStopped`. Never release a claim or accept
a replacement response.

- [ ] **Step 5: Implement narrative guards and reconciliation packet**

After valid code judgment only:

1. persist the validated frozen `CodeJudgment`;
2. hash/read ledger, active prior report, deferred summary paths, and explicit
   narrative paths;
3. parse D entries and closed probe declarations;
4. derive whether prior acceptance QA exists from guarded artifacts;
5. issue a reconciliation packet/schema and new one-use nonce; and
6. return `NeedJudgment(kind="reconciliation")`.

Do not execute a probe, aggregate, render, or write a report in this task.

- [ ] **Step 6: Run focused and cumulative suites**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_*.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_policy.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
git diff --check
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```text
git add check-contract/scripts/audit_runtime.py \
  check-contract/scripts/audit_reconciliation.py \
  check-contract/tests/test_audit_runtime_reconciliation.py
git commit -m "feat: reconcile contract narratives after code"
```

---

### Task 6: Close and publish a single-target audit

**Files:**

- Modify: `check-contract/scripts/audit_runtime.py`
- Create: `check-contract/scripts/probe_runner.py`
- Create: `check-contract/scripts/audit_report.py`
- Create: `check-contract/tests/test_audit_runtime_close.py`

**Interfaces:**

- Consumes: a reconciliation `NeedJudgment` and exact response envelope
- Produces: `AuditComplete` or `AuditStopped`

- [ ] **Step 1: Write failing probe/aggregation tests**

Require that a reconciliation judgment:

- covers exactly every D ID and deviation match;
- may select zero or one issued probe ID;
- cannot submit argv, shell, code, route, verdict, report path, or aggregate;
- cannot mark a probe-required D `VERIFIED` without selecting its probe;
- runs the selected descriptor once from `git archive <recorded-head>`;
- uses a runtime-owned no-shell Python runner, fixed environment,
  `PYTHONDONTWRITEBYTECODE=1`, and bounded timeout;
- removes the disposable tree and creates no target pycache; and
- makes probe failure an observed `QUESTIONABLE`, never a retry.

- [ ] **Step 2: Write failing freshness/publication tests**

Cover HEAD, authority, contract, ledger, summary, status, prior-report, packet,
and source guard drift. Each mismatch preserves the prior report.

For every scenario require deterministic report bytes, exact stable U/F/D IDs,
all report sections, exact verdict/route, atomic `os.replace`, and a final
mutation set containing only the active report. Required validation alone is
not a YAGNI item.

- [ ] **Step 3: Verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_close.py' -v
```

Expected: FAIL because reconciliation close/publication does not exist.

- [ ] **Step 4: Implement strict reconciliation validation and probe runner**

The inner judgment contains exactly:

```json
{
  "ledger_entries": {},
  "deviation_matches": [],
  "contract_obsolete": {
    "value": false,
    "evidence_ids": [],
    "reason": "..."
  },
  "probe_id": null
}
```

Each ledger entry contains closed status, evidence IDs, and reason. The
runtime, not the model, supplies `acceptance_qa_exists`. If a selected issued
probe succeeds, its probe-required D may remain `VERIFIED`; failure or absence
makes it `QUESTIONABLE`.

- [ ] **Step 5: Implement freshness, deterministic report, and atomic write**

Rerun shared authority resolution and every byte/hash/status guard immediately
before publication. Render outside the target, then use
`tempfile.mkstemp(dir=report.parent)` plus `os.replace`. Remove an unpublished
temporary in all failure paths.

After replacement, attest that initial target state plus the active report is
the exact final state. Return `AuditComplete` with policy-owned verdict/route,
report digest, and immutable mutation attestation.

- [ ] **Step 6: Run scenario and shared suites**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_*.py' -v
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```text
git add check-contract/scripts/audit_runtime.py \
  check-contract/scripts/probe_runner.py \
  check-contract/scripts/audit_report.py \
  check-contract/tests/test_audit_runtime_close.py
git commit -m "feat: publish deterministic contract audit reports"
```

---

### Task 7: Enforce compound closure and expose the thin CLI

**Files:**

- Modify: `check-contract/scripts/audit_runtime.py`
- Create: `check-contract/scripts/check_contract.py`
- Create: `check-contract/tests/test_audit_runtime_compound.py`
- Create: `check-contract/tests/test_check_contract_cli.py`

**Interfaces:**

```text
python check-contract/scripts/check_contract.py start \
  --repo R --branch B --ticket T \
  [--narrative PATH ...] \
  [--then-repo R2 --then-branch B2 --then-ticket T2] \
  [--then-narrative PATH ...] \
  [--deadline-seconds N]

python check-contract/scripts/check_contract.py continue \
  --session OPAQUE --response RESPONSE_JSON
```

- [ ] **Step 1: Write failing compound erasure tests**

For invalid A then valid B:

```python
first = runtime.advance(StartAudit(primary=invalid_a, then=valid_b))
self.assertEqual(first.target, "then")
self.assertEqual(first.kind, "code")
self.assertTrue(first.a_closure_digest)
self.assertNotIn(str(invalid_a.repo), json.dumps(packet_of(first)))
```

Require A zero-write/prior-report-preserved attestation before any B action,
then no later A filesystem/Git call. B generation contains only the opaque A
closure digest—no A path, identity, SHA, sentinel, clause, finding, authority
text, or capability.

For valid A then valid B, B begins only after A is published and `Closed`.
The public transition may expose only a path-free closure summary:

```json
{
  "target": "primary",
  "outcome": "closed | authority-stopped",
  "zero_writes": true,
  "report_only_write": false,
  "prior_report_preserved": true,
  "closure_digest": "..."
}
```

For a published valid A, `zero_writes` is false and `report_only_write` is
true. For an authority-stopped A, `zero_writes` is true,
`report_only_write` is false, and `prior_report_preserved` is true.

- [ ] **Step 2: Write failing CLI tests**

Require canonical JSON output, installed-sibling discovery from script
location, foreign-cwd operation, exact start/continue args, exit `0` for
`NeedJudgment`/`AuditComplete`, exit `2` for `AuditStopped`, and no secrets or
target capabilities in output.

- [ ] **Step 3: Verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_compound.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_check_contract_cli.py' -v
```

Expected: FAIL because compound transition and CLI do not exist.

- [ ] **Step 4: Implement target-stop versus run-stop**

- Target authority hard stop: seal zero-write/prior-report preservation,
  hash and erase target state, then allow `then`.
- Run stop: session integrity, storage, deadline, or runtime failure returns
  `AuditStopped` and never starts `then`.
- Valid target close: publish/attest, hash and erase target state, then allow
  `then`.

Start B in a new random run directory. No B token or generation references the
A run directory or generation; only the closure digest and path-free summary
cross the boundary.

- [ ] **Step 5: Implement the thin CLI**

The CLI parses args, derives sibling `change-contract` from its absolute
installed script location, calls only `AuditRuntime.advance`, and prints
canonical JSON:

```python
def main(argv=None):
    args = parser().parse_args(argv)
    result = runtime_from_script_location().advance(command_from(args))
    print(json.dumps(as_public_dict(result), sort_keys=True))
    return 0 if isinstance(result, (NeedJudgment, AuditComplete)) else 2
```

- [ ] **Step 6: Run the full runtime/shared suites**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```text
git add check-contract/scripts/audit_runtime.py \
  check-contract/scripts/check_contract.py \
  check-contract/tests/test_audit_runtime_compound.py \
  check-contract/tests/test_check_contract_cli.py
git commit -m "feat: expose compound contract audit runtime"
```

---

### Task 8: Replace prompt choreography with runtime choreography

**Files:**

- Modify: `check-contract/SKILL.md`
- Modify: `check-contract/tests/test_skill_contract.py`
- Modify: `check-contract/evals/README.md`

**Interfaces:**

- Consumes: Task 7 CLI public envelopes
- Produces: an explicit-only skill that performs no direct repository
  inspection and follows only runtime-issued packets/next commands

- [ ] **Step 1: Replace prose-structure tests with behavior-bearing skill tests**

Remove tests that require six prose headings. Add exact constraints:

```python
def test_skill_is_thin_runtime_choreography(self):
    for phrase in (
        "scripts/check_contract.py start",
        "scripts/check_contract.py continue",
        "NeedJudgment",
        "AuditComplete",
        "AuditStopped",
        "runtime-issued evidence IDs",
        "do not inspect the target repository directly",
        "do not choose the verdict or route",
        "do not retry",
    ):
        self.assertIn(phrase, self.skill)
    self.assertNotIn("git diff ", self.skill)
    self.assertNotIn("git show ", self.skill)
    self.assertNotIn("git grep ", self.skill)
```

Require at most 500 words and installed-sibling portability.

- [ ] **Step 2: Run the focused skill tests and verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_skill_contract.py' -v
```

Expected: FAIL because the skill still owns the six-step prompt workflow.

- [ ] **Step 3: Rewrite `SKILL.md` around the continuation protocol**

The skill must contain only:

1. explicit invocation/report-only safety boundary;
2. absolute script resolution from the loaded skill directory;
3. one `start` command for the primary and optional `then` target;
4. reading the issued code packet and writing exactly its closed response
   schema using only issued evidence IDs;
5. one `continue`;
6. reading the issued reconciliation packet and writing exactly its closed
   response schema, selecting at most one issued probe ID;
7. the final `continue`;
8. surfacing `AuditComplete` or `AuditStopped` exactly;
9. no repository commands, direct report writing, aggregate calculation,
   route selection, retry, or recommended-skill invocation.

For a compound request, pass both targets to one `start`; never create a second
runtime session.

- [ ] **Step 4: Run all structural and unit suites**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
wc -w check-contract/SKILL.md
git diff --check
```

Expected: all tests PASS, skill is at most 500 words, diff check clean.

- [ ] **Step 5: Commit**

```text
git add check-contract/SKILL.md \
  check-contract/tests/test_skill_contract.py \
  check-contract/evals/README.md
git commit -m "refactor: drive check-contract through runtime"
```

---

### Task 9: Run immutable behavioral acceptance and benchmark the runtime

**Files:**

- Create ignored: `check-contract-workspace/iteration-4/**`
- Create: `.superpowers/sdd/check-contract-runtime-eval-report.md`
- Do not modify product files while trials are running

**Interfaces:**

- Consumes: exact reviewed Task 8 HEAD, assertion contract v2, isolated runner
- Produces: 18 immutable paired samples, objective grades, benchmark JSON/MD,
  static review viewer, and independent causal/acceptance verdict

- [ ] **Step 1: Freeze the reviewed runtime snapshot**

Record the exact HEAD and SHA-256 for:

```text
check-contract/SKILL.md
check-contract/scripts/check_contract.py
check-contract/scripts/audit_runtime.py
change-contract/references/contract-protocol.md
change-contract/references/contract-check-rules.json
change-contract/scripts/contract_state.py
```

Mount only this snapshot read-only for treatment. Controls receive no runtime
or skill.

- [ ] **Step 2: Run preflight and fresh paired trials**

Use the existing neutral prompts, Claude Code version/model/effort, bubblewrap
isolation, fresh materialized fixtures, unique sessions, maximum concurrency
two, and canonical 360-second harness timeout.

Run exactly:

- 3 scenarios × 3 treatment samples;
- 3 scenarios × 3 fresh paired control samples.

Accept each first behavioral outcome exactly once. Never overwrite, retry,
replace, or silently quarantine a behavioral failure. Infrastructure failures
may be quarantined only with objective provider/runner evidence before a
replacement starts.

- [ ] **Step 3: Grade actions, filesystem, reports, and runtime envelopes**

Persist one `grading.json` per accepted sample. Grade:

- authority and code/narrative chronology from runtime events;
- packet/response phase order and single-use nonces;
- exact filesystem before/after state;
- report delivery separately from mutation scope;
- clause/axis/verdict/route semantics;
- A, B, AB1, and compound using disjoint slices;
- timeout as full-sample failure; and
- no inferred success from terminal prose.

- [ ] **Step 4: Build the benchmark and viewer**

Report assertion totals, exact full-sample totals, per-scenario rates,
duration, terminal token/cost observations with null timeout handling,
population variance/SD, compound slices, and treatment-control deltas.

Lead with:

```text
Required: 9/9 treatment samples pass every critical assertion
Observed: <n>/9
```

- [ ] **Step 5: Obtain an independent causal and acceptance review**

The reviewer independently verifies prompt parity, snapshot hashes, isolation,
accepted inventory/no retries, filesystem recapture, action chronology,
grades, arithmetic, timeout handling, and false reassurance.

Acceptance requires both:

```text
9/9 treatment full samples
independent ACCEPT
```

If either fails, do not install or claim Task 9 complete. Diagnose the repeated
runtime defect, add a behavior-level failing regression, implement the minimum
fix in a new reviewed commit, and run a new immutable iteration directory.
Never rewrite or selectively rerun the failed iteration.

- [ ] **Step 6: Record completion or explicit failed gate**

Write `.superpowers/sdd/check-contract-runtime-eval-report.md` with exact
provenance, results, failures, and reviewer verdict. A failed gate remains an
incomplete task; partial gains are evidence only.

---

### Task 10: Install and document only the accepted runtime

**Files:**

- Modify: `README.md`
- Update installed copies under the repository's established install roots
- Create: `.superpowers/sdd/check-contract-runtime-install-report.md`

**Interfaces:**

- Consumes: Task 9's 9/9 + independent ACCEPT
- Produces: source/install byte parity and discoverable `/check-contract`

- [ ] **Step 1: Gate installation on accepted evidence**

Read the Task 9 report and independently require the exact accepted HEAD,
9/9 treatment full passes, no hidden retries, and reviewer ACCEPT. Stop if any
field is missing.

- [ ] **Step 2: Update discovery docs**

Describe `/check-contract` as a report-only, code-first audit of shipped code
against an immutable approved contract. State its exact verdicts and routes,
and that it does not fix or invoke the recommendation.

- [ ] **Step 3: Install all runtime siblings atomically**

Install `check-contract` and the changed shared `change-contract` reference
files using the repository's established installer. Ensure the installed
relative layout keeps sibling discovery valid.

- [ ] **Step 4: Verify source/install parity and smoke behavior**

Compare SHA-256 for every installed runtime file. From outside the skills
repository:

```text
python <installed-check-contract>/scripts/check_contract.py --help
python <installed-change-contract>/scripts/contract_state.py --help
```

Run one disposable approved-fixture three-call smoke audit and verify only the
active report changes.

- [ ] **Step 5: Run final suites and commit docs**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
git status --short
```

Expected: all tests PASS; only intentional source changes are present.

```text
git add README.md
git commit -m "docs: publish deterministic check-contract workflow"
```

Record installed paths, hashes, smoke output, and accepted benchmark provenance
in `.superpowers/sdd/check-contract-runtime-install-report.md`.

---

## Plan Self-Review

- **Spec coverage:** immutable authority, report-only mutation, code-first
  separation, deterministic aggregation/routing, YAGNI/reuse ownership,
  bounded probe execution, A→B closure, deadline/no-retry behavior,
  behavioral acceptance, installation gate, and eval caveats each map to a
  task and test.
- **YAGNI:** one runtime, one CLI, two judgment schemas, one JSON policy pack;
  no provider integration or general adapter framework.
- **Type consistency:** `AuditRuntime.advance` is the sole workflow API;
  `start` creates `NeedJudgment(kind="code")`, first `continue` creates
  `NeedJudgment(kind="reconciliation")`, second `continue` creates
  `AuditComplete` or `AuditStopped`.
- **No placeholders:** every product task names exact files, interfaces,
  tests, commands, expected results, and commit boundaries.
- **Workflow immutability:** old iterations are never rewritten; failed new
  iterations remain accepted evidence; installation is impossible before
  exact 9/9 plus independent acceptance.
