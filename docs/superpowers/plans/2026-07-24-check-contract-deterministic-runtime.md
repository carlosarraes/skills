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
| `check-contract/scripts/audit_runtime.py` | Deep continuation runtime, private phase machine, evidence capture, policy application, publication |
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
    finding_ids: tuple[str, ...]


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

The validator must require:

- exactly the runtime-issued clause IDs and changed-path IDs;
- only closed enum values;
- only issued evidence IDs;
- fidelity namespace ownership;
- non-empty reason text;
- no aggregate, verdict, route, report-path, or mutation fields; and
- no extra JSON keys.

- [ ] **Step 5: Make the protocol point to executable truth**

Keep the human-readable semantics in
`contract-protocol.md`, but replace duplicated enum/precedence tables with:

```markdown
`contract-check-rules.json` is the executable source of truth for closed
enums, evidence-namespace ownership, aggregation order, route precedence, and
report schema version. This section explains those rules; consumers must load
and validate the JSON rather than scraping Markdown.
```

- [ ] **Step 6: Run policy and existing protocol suites**

Run:

```text
python -m unittest discover -s check-contract/tests -p 'test_audit_policy.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```text
git add change-contract/references/contract-check-rules.json \
  change-contract/references/contract-protocol.md \
  check-contract/scripts/audit_runtime.py \
  check-contract/tests/test_audit_policy.py
git commit -m "feat: add deterministic contract audit policy"
```

---

### Task 3: Implement the immutable continuation runtime and CLI

**Files:**

- Modify: `check-contract/scripts/audit_runtime.py`
- Create: `check-contract/scripts/check_contract.py`
- Create: `check-contract/tests/runtime_fixtures.py`
- Create: `check-contract/tests/test_audit_runtime.py`
- Create: `check-contract/tests/test_check_contract_cli.py`

**Interfaces:**

- Consumes:
  `contract_state.resolve_consumer(repo, branch, ticket,
  allow_missing_ledger=True)` and Task 2's rule pack/kernel
- Produces:

```python
AuditRuntime.advance(
    StartAudit | ContinueAudit
) -> NeedJudgment | AuditComplete | AuditStopped
```

CLI:

```text
python check-contract/scripts/check_contract.py start \
  --repo R --branch B --ticket T \
  [--then-repo R2 --then-branch B2 --then-ticket T2] \
  [--deadline-seconds N]

python check-contract/scripts/check_contract.py continue \
  --session OPAQUE --response RESPONSE_JSON
```

- [ ] **Step 1: Build reusable temporary-repository fixtures**

`runtime_fixtures.py` must create approved repositories by calling the
canonical check-contract materializer, never by duplicating contract state.
Expose:

```python
def materialized_repo(scenario: str, target: str = "target") -> ContextManager[Path]:
    ...


def valid_code_response(packet: dict, *, overrides: dict | None = None) -> dict:
    ...


def valid_reconciliation_response(
    packet: dict, *, overrides: dict | None = None
) -> dict:
    ...
```

- [ ] **Step 2: Write failing phase and mutation tests**

Cover at minimum:

```python
def test_three_calls_publish_only_active_report(self):
    first = self.runtime.advance(StartAudit(...))
    self.assertEqual(first.kind, "code")
    self.assertFalse(report_path.exists())

    second = self.runtime.advance(
        ContinueAudit(first.session, valid_code_response(first.packet))
    )
    self.assertEqual(second.kind, "reconciliation")
    self.assertFalse(report_path.exists())

    final = self.runtime.advance(
        ContinueAudit(second.session,
                      valid_reconciliation_response(second.packet))
    )
    self.assertIsInstance(final, AuditComplete)
    self.assertEqual(final.verdict, "NEEDS HUMAN REVIEW")
    self.assertEqual(final.route, ("clean-up",))
    self.assertEqual(changed_paths(repo), {active_report_path})
```

Also test:

- code packet contains no ledger, summary, PR, or prior-report bytes;
- reconciliation packet is unavailable before valid code judgment;
- invalid, duplicate, stale, wrong-session, and out-of-phase responses stop;
- missing evidence IDs and extra response keys stop;
- expired deadline stops without writing;
- authority/hash/identity/ancestry failure preserves a sentinel report;
- HEAD, contract, ledger, summary, status, or prior-report freshness drift
  stops without replacement;
- a dirty worktree is disclosed and remains byte-identical;
- a replay probe is selected only by issued ID, runs once without shell in an
  archived recorded-HEAD tree, and cannot create target pycache;
- an undeclared probe or second probe stops;
- deterministic report bytes are identical across repeated fresh fixtures;
- required validation cannot become a YAGNI item without explicit unearned
  evidence;
- the overengineered scenario routes to `clean-up`;
- the violated-summary scenario routes to `exec-ticket`; and
- the documented-drift scenario routes to `qa-ticket`.

- [ ] **Step 3: Write failing compound closure tests**

Test the exact pressure case:

```python
def test_invalid_a_is_sealed_before_b_and_never_revisited(self):
    first = self.runtime.advance(
        StartAudit(primary=invalid_a, then=valid_b)
    )
    self.assertEqual(first.target, "then")
    self.assertEqual(first.kind, "code")
    self.assertTrue(first.a_closure_digest)
    self.assertNotIn(str(invalid_a.repo), json.dumps(first.packet))

    finish_b(first)
    self.assertEqual(self.runner.calls_for_repo(invalid_a.repo),
                     calls_before_b_started)
    self.assertEqual(invalid_a.report.read_bytes(), sentinel)
```

For two valid targets, assert B does not start until A is `Closed`. B state may
contain only the opaque A closure digest; it must contain no A path, SHA,
sentinel, clause, finding, or authority text.

- [ ] **Step 4: Run runtime tests and verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_check_contract_cli.py' -v
```

Expected: FAIL because the continuation runtime and CLI do not exist.

- [ ] **Step 5: Implement the public continuation envelopes**

Use frozen dataclasses:

```python
@dataclass(frozen=True)
class AuditTarget:
    repo: Path
    branch: str
    ticket: str


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
    a_closure_digest: str | None = None


@dataclass(frozen=True)
class AuditComplete:
    verdict: str
    route: tuple[str, ...]
    report_path: Path
    report_sha256: str
    mutation_attestation: dict


@dataclass(frozen=True)
class AuditStopped:
    code: str
    reason: str
    target: str
    prior_report_preserved: bool
    zero_target_writes: bool
```

`AuditRuntime.advance` is the sole public workflow method.

- [ ] **Step 6: Implement private monotonic phases and sealed sessions**

Private phase values:

```python
class _Phase(str, Enum):
    AUTHORITY_GUARDED = "authority_guarded"
    CODE_FROZEN = "code_frozen"
    CODE_JUDGED = "code_judged"
    NARRATIVE_GUARDED = "narrative_guarded"
    RECONCILED = "reconciled"
    AGGREGATED = "aggregated"
    FRESH = "fresh"
    PUBLISHED = "published"
    CLOSED = "closed"
    STOPPED = "stopped"
```

The session directory is created with mode `0700` outside all targets.
Runtime-owned state is canonical JSON plus a SHA-256 manifest and is chmod
read-only before return. The response path is separate and absent at return.
On continuation, verify the manifest, packet hash, response session, phase,
deadline, and one-use nonce before changing state.

- [ ] **Step 7: Implement bounded Git-object evidence capture**

At start:

1. resolve canonical root and approved authority with the shared resolver;
2. record full base/HEAD and exact guard bytes/hashes;
3. capture one name-status inventory with rename detection;
4. capture one path-filtered base..HEAD diff and recorded-HEAD blobs for
   changed implementation source/tests;
5. capture one full-HEAD repository-wide reuse search result;
6. issue typed evidence IDs such as
   `behavior:BLOB-0001`, `public-contract:DIFF-0002`,
   `risk:BLOB-0003`, `acceptance:TEST-0004`,
   `surface:PATH-0005`, `complexity:PATH-0005`, and
   `reuse:SEARCH-0006`;
7. freeze partial evidence as indeterminate if the evidence deadline expires;
8. only after the code account is frozen, parse the approved contract and
   return the code packet.

No packet contains narrative contents or a writable target capability.

- [ ] **Step 8: Implement reconciliation, probe, freshness, and publication**

After a valid code response:

1. guard and read ledger, supplied summary/PR narrative when explicitly
   supplied, and prior report;
2. parse ledger D entries and conservative shell-free probe candidates;
3. return the reconciliation packet;
4. validate the reconciliation response and optional issued probe ID;
5. execute the selected exact argv once in an outside-repository archived
   tree with `PYTHONDONTWRITEBYTECODE=1`;
6. aggregate axes/verdict/route from the policy pack;
7. rerun authority resolution and every guard;
8. render the report outside the target;
9. atomically replace only the active `check-report.md`;
10. compare the final target state with the initial state plus that one path;
11. close the target, then either start `then` or return `AuditComplete`.

Use `tempfile.mkstemp(dir=report.parent)` plus `os.replace`; always remove an
unpublished temporary.

- [ ] **Step 9: Implement the thin JSON CLI**

`check_contract.py` only parses arguments, calls `AuditRuntime.advance`, and
prints canonical JSON:

```python
def main(argv=None):
    args = parser().parse_args(argv)
    result = runtime_from_script_location().advance(command_from(args))
    print(json.dumps(as_public_dict(result), sort_keys=True))
    return 0 if isinstance(result, (NeedJudgment, AuditComplete)) else 2
```

It must derive sibling `change-contract` from the absolute installed
`check-contract` script location, not cwd.

- [ ] **Step 10: Run runtime, CLI, and shared suites**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_*.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_check_contract_cli.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
```

Expected: all tests PASS and diff check is clean.

- [ ] **Step 11: Commit**

```text
git add check-contract/scripts check-contract/tests/runtime_fixtures.py \
  check-contract/tests/test_audit_runtime.py \
  check-contract/tests/test_check_contract_cli.py
git commit -m "feat: enforce immutable contract audit runtime"
```

---

### Task 4: Replace prompt choreography with runtime choreography

**Files:**

- Modify: `check-contract/SKILL.md`
- Modify: `check-contract/tests/test_skill_contract.py`
- Modify: `check-contract/evals/README.md`

**Interfaces:**

- Consumes: Task 3 CLI public envelopes
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

### Task 5: Run immutable behavioral acceptance and benchmark the runtime

**Files:**

- Create ignored: `check-contract-workspace/iteration-4/**`
- Create: `.superpowers/sdd/check-contract-runtime-eval-report.md`
- Do not modify product files while trials are running

**Interfaces:**

- Consumes: exact reviewed Task 4 HEAD, assertion contract v2, isolated runner
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

If either fails, do not install or claim Task 5 complete. Diagnose the repeated
runtime defect, add a behavior-level failing regression, implement the minimum
fix in a new reviewed commit, and run a new immutable iteration directory.
Never rewrite or selectively rerun the failed iteration.

- [ ] **Step 6: Record completion or explicit failed gate**

Write `.superpowers/sdd/check-contract-runtime-eval-report.md` with exact
provenance, results, failures, and reviewer verdict. A failed gate remains an
incomplete task; partial gains are evidence only.

---

### Task 6: Install and document only the accepted runtime

**Files:**

- Modify: `README.md`
- Update installed copies under the repository's established install roots
- Create: `.superpowers/sdd/check-contract-runtime-install-report.md`

**Interfaces:**

- Consumes: Task 5's 9/9 + independent ACCEPT
- Produces: source/install byte parity and discoverable `/check-contract`

- [ ] **Step 1: Gate installation on accepted evidence**

Read the Task 5 report and independently require the exact accepted HEAD,
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
