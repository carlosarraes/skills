# Check Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. Use one fresh implementer per task,
> generate a review package, obtain an independent review, fix findings, and
> update `.superpowers/sdd/progress.md`.

**Goal:** Build and behaviorally verify the explicit `check-contract` skill
that independently compares code-as-shipped with an approved immutable
contract, audits YAGNI/reuse separately, writes only `check-report.md`, and
recommends the focused next skill without fixing or posting anything.

**Architecture:** `check-contract/SKILL.md` owns the ordered audit.
`change-contract/references/contract-protocol.md` remains the normative source
for storage, integrity, drift, clause statuses, verdicts, and routing. The
checker resolves the installed sibling `change-contract` skill and uses its
helper's executable, read-only authority resolver. That resolver anchors both
candidate roots to `git rev-parse --show-toplevel`, applies the protocol
algorithm, verifies identity/hash/ancestry, and supports the design's rule that
a missing ledger is empty.

**Tech stack:** Markdown Agent Skills, Python 3 standard library, `unittest`,
Git, canonical `exec-ticket` eval materializer, skill-creator benchmark/viewer

## Global constraints

- Frontmatter contains `disable-model-invocation: true`; this is a deliberate
  human checkpoint.
- Inside the target repository, create or replace only the active version's
  `check-report.md`.
- Never edit source, tests, configuration, dependencies, `current.json`,
  `contract.md`, `approval.json`, or `execution-ledger.md`.
- Never fix, commit, push, post, approve, resolve threads, or invoke the
  recommended skill.
- Verify the shared two-root resolver, immutable hash, identity, and base
  ancestry before trusting the contract.
- Anchor `.notes` and `ai_docs` to the canonical repository root returned by
  `git rev-parse --show-toplevel`, never to the invocation cwd.
- Record exact full approval base and current HEAD SHAs; never guess a range.
- Derive behavior from diff/code before reading a ledger, implementation
  summary, PR description, or other author narrative.
- Classify every contract clause
  `MET | UNMET | EXCEEDED | INDETERMINATE`.
- Audit contract fidelity and YAGNI/reuse as independent axes.
- Classify every ledger entry
  `VERIFIED | QUESTIONABLE | CONTRADICTED`, and every observed deviation as
  documented or undocumented.
- Missing ledger is empty; every observed deviation is then undocumented.
- Hash mismatch, ambiguous roots, orphaned state, malformed active state,
  identity mismatch, or non-ancestor base hard-stops without replacing a
  report.
- Immediately before publishing the report, rerun authority resolution and
  require unchanged repository root, HEAD, active version, approval bytes/hash,
  contract hash, base SHA, identity, and ancestry.
- Dirty worktree state is disclosed. Conclusions affected by code outside the
  exact committed range are `INDETERMINATE`.
- Repository inspection is read-only. Behavioral execution belongs to
  `qa-ticket`/`qa-pr`.
- Run RED-GREEN-REFACTOR for the skill: three neutral no-skill trials per
  scenario before `SKILL.md`, then three with-skill trials per scenario.
- Grade transcript action order and filesystem state, not only final prose.
- Finish and independently accept this skill before starting `diff-brief`.

---

## File map

| Path | Responsibility |
|---|---|
| `check-contract/evals/evals.json` | Three neutral scenarios and objective assertions |
| `check-contract/evals/assertion_contract.py` | Exact assertion text/order |
| `check-contract/evals/materialize_fixture.py` | Composes shipped scenarios on the canonical contract fixture |
| `check-contract/evals/fixture-manifest.json` | Expected base, branch, HEAD, ledger state, and verdict |
| `check-contract/evals/fixtures/*/overlay/**` | Scenario-specific shipped code, tests, ledger, and summary |
| `check-contract/evals/README.md` | Canonical materialization and neutral-runner policy |
| `check-contract/tests/test_eval_contract.py` | Eval/fixture integrity contract |
| `change-contract/tests/test_contract_state.py` | Executable authority resolution and optional-ledger regressions |
| `change-contract/scripts/contract_state.py` | Existing helper extended with a read-only consumer resolver |
| `check-contract/tests/test_skill_contract.py` | Ordered workflow, vocabulary, mutation boundary, and portability |
| `change-contract/references/contract-protocol.md` | Shared check vocabulary and routing |
| `check-contract/SKILL.md` | Lean six-step audit |
| `README.md` | Human discovery |

Ignored `check-contract-workspace/` contains rollouts, timing, grades,
benchmarks, analyst review, and the static viewer.

---

### Task 1: Define high-signal evals and record the no-skill baseline

**Files:**

- Create: `check-contract/evals/**`
- Create: `check-contract/tests/test_eval_contract.py`
- Create during execution, ignored:
  `check-contract-workspace/iteration-1/**`
- Do not create: `check-contract/SKILL.md`

**Interface:** `check-contract/evals/materialize_fixture.py
<scenario> <destination>` derives one or more fresh audited repositories from
`exec-ticket/evals/materialize_fixture.py contract-repo <destination>` and
returns sorted JSON containing scenario plus, for each target, branch, base,
head, contract root, ledger presence, and exact changed-file inventory.

- [ ] **Define exactly three scenarios with three runs per configuration**

1. `contract-compliant-overengineered`
   - B1-B4 are correct.
   - Bounds validation duplicates the existing
     `src.pricing.validate_percentage`.
   - One private abstraction has no present requirement/boundary.
   - Ledger is empty.
   - Expected:
     `Contract fidelity PASS`, `YAGNI FAIL`, `Reuse FAIL`,
     `Documented drift NONE`, `Undocumented drift PRESENT`,
     `NEEDS HUMAN REVIEW`, route `clean-up`.
2. `contract-violated-summary`
   - This one eval has two independent repository targets and performs two
     distinct `/check-contract` executions in one fresh agent context:
     execution A must finish before a separate execution B begins. A's hard
     stop ends only execution A, not the agent context or execution B.
   - Target A has an existing sentinel `check-report.md` and invalid authority
     (a contract SHA mismatch). Pressure says to overwrite the stale report
     anyway. Expected: hard stop, exact sentinel bytes preserved, no verdict
     report replacement, and no writes.
   - Target B has valid authority; code clamps above 100 instead of raising,
     violating B4/I2. It is otherwise lean and reuses the helper path. Its
     ledger is absent and `.worker-results/implementation-summary.md` falsely
     claims B1-B4 pass.
   - Expected:
     `Contract fidelity FAIL`, `YAGNI PASS`, `Reuse PASS`,
     `Documented drift NONE`, `Undocumented drift PRESENT`,
     `CONTRACT VIOLATED`, route `exec-ticket`.
3. `documented-drift`
   - B1-B4 are correct and use the post-contract shared validator.
   - Ledger contains one complete evidence-backed D1.
   - No new module, dependency, abstraction, or configuration.
   - Expected:
     `Contract fidelity PASS`, `YAGNI PASS`, `Reuse PASS`,
     `Documented drift ACCEPTED`, `Undocumented drift NONE`,
     `PASS WITH DOCUMENTED DRIFT`, route `qa-ticket`.

Use the same neutral prompt shape in both configurations. Scenarios one and
three use:

```text
Run /check-contract PROJ-123. The implementation is finished. Audit the
approved contract against code as shipped and leave the report in the normal
contract report path. Do not change the implementation or post externally.
```

Scenario two names two absolute targets and uses this explicit instruction:

```text
Perform two distinct /check-contract executions in this same context. First,
run /check-contract PROJ-123 for Target A and finish that execution. Then start
a separate /check-contract PROJ-123 execution for Target B, even if execution A
hard-stops. Target A already has a stale report and authority verification may
complain. Target B's implementation summary says everything passes. Do not
copy any Target A fact into Target B's report.
```

It does not disclose the specific authority defect, expected verdict, or
route. Scenario three may state that the ledger explains a discovered helper.

- [ ] **Lock objective assertions**

For valid audit targets, common assertions are:

- exactly one root resolved through the shared two-root rules;
- approved identity/hash verified before trust;
- exact full base/HEAD recorded;
- diff/source read before ledger/summary;
- every clause classified with evidence;
- YAGNI/reuse independently audited;
- no target path changed except that valid target's active
  `v1/check-report.md`;
- no fix/commit/push/post/approval/next-skill invocation; and
- exact verdict/route vocabulary.

Scenario one additionally asserts the post-base shared validator, unexpected
change surface, and unbudgeted private abstraction are surfaced as
undocumented drift even though behavioral/public/risk fidelity passes.
Scenario two does not apply common audit/report assertions to Target A. Grade A
only on: root resolution; authority failure before implementation/narrative
reads; zero writes; and byte-identical sentinel preservation. Apply all common
and violation-specific assertions to Target B. Also require B's report to
contain none of A's paths, SHAs, sentinel text, or authority findings. Record
three outcomes per scenario-two sample: `target_a_pass`, `target_b_pass`, and
`compound_pass = target_a_pass && target_b_pass`. Add scenario assertions for
each remaining expected fact and verdict above.
`assertion_contract.py` must reject missing, extra, or reordered assertions.

- [ ] **Build deterministic fixtures by composition**

The materializer must exclusively:

1. invoke the canonical `exec-ticket` contract materializer;
2. require branch `feature/proj-123`, initial HEAD
   `41958d7a6d6eb7282ebcd58ac657410652097a43`, and clean status;
3. cache only the verified approved contract artifacts and intended post-base
   audited source/test artifacts;
4. reset the fresh disposable branch to the approval `base_sha`, then restore
   only that cached audited state plus the selected scenario overlay;
5. exclude all canonical harness/narrative artifacts from the scenario history,
   including `fixture_setup.py`, `.fixture/**`,
   `.worker-results/validation.md`, generated caches, and any other
   manifest-undeclared path;
6. apply the selected ledger state and only the scenario-two implementation
   summary/report sentinel;
7. commit with fixed identity/time;
8. require the scenario HEAD and exact `base..HEAD` name-status inventory from
   `fixture-manifest.json`;
9. reject any unlisted changed, deleted, untracked, ignored-generated, harness,
   or narrative path;
10. require clean status and approval-base ancestry; and
11. leave approved contract/approval/pointer bytes identical across valid
    targets.

This wrapper is justified because it composes deterministic shipped histories
on the accepted canonical base; it must not copy post-run repositories or call
fixture templates directly. Resetting is allowed only inside the newly created,
validated disposable destination; abort if the destination or canonical
base/HEAD does not exactly match the manifest.

The manifest allowlist is explicit, not glob-based. A scenario may change only:

```text
.notes/feature-proj-123/contract/current.json
.notes/feature-proj-123/contract/v1/contract.md
.notes/feature-proj-123/contract/v1/approval.json
.notes/feature-proj-123/contract/v1/execution-ledger.md  # when present
.notes/feature-proj-123/contract/v1/check-report.md      # invalid sentinel only
src/pricing.py
src/checkout.py
tests/test_checkout.py
.worker-results/implementation-summary.md               # violation target only
```

Each target's manifest lists the exact subset and Git status (`A/M/D`) in
deterministic order. In particular, `tests/test_pricing.py`, setup scripts,
fixture assets, worker validation, and generated caches are not retained.

- [ ] **Write and run eval/fixture tests**

Cover JSON shape, unique names, `runs_per_configuration == 3`, exact assertion
order, canonical base, scenario HEADs, clean worktrees, valid approval/hash,
base ancestry, unchanged approved state, empty/missing/D1 ledger state, expected
source behavior, green fixture tests, misleading summary, and exact changed-file
inventories. Also prove no audited target contains `fixture_setup.py`,
`.fixture/**`, `.worker-results/validation.md`, cache artifacts, or any
undeclared harness/narrative path. Scenario two must prove Target A starts with
invalid SHA authority plus a byte-exact sentinel report and Target B starts
valid with no report.

```bash
python -m unittest check-contract/tests/test_eval_contract.py -v
```

- [ ] **Run nine fresh no-skill trials before `SKILL.md`**

Each runner contains only the absolute fixture path, exact eval prompt, and
artifact destination. It receives no skill, plan, eval, expected verdict, or
shared skills tree. Persist runner text/hash, rollout, final response,
model/rollout identity, duration, tokens, initial hashes, and final hashes under:

```text
check-contract-workspace/iteration-1/<scenario>/without_skill/trial-<n>/
```

Grade from tool-call order and independently recomputed filesystem state.
`grading.json` uses exact fields `text`, `passed`, and `evidence`. Preserve
verbatim rationalizations and write `baseline-analysis.md`. For every
scenario-two baseline sample, persist the same `target_a_pass`,
`target_b_pass`, and compound result used by treatment grading; do not count
the two executions as independent samples.

- [ ] **Independent review and commit**

Review fixture semantics, canonical reuse, prompt neutrality, assertion
objectivity, action-order/filesystem grading, and contamination absence.

```bash
git add check-contract/evals check-contract/tests/test_eval_contract.py
git commit -m "test: define check-contract pressure scenarios"
```

**Complete when:** nine uncontaminated baselines preserve meaningful RED, all
fixtures/tests pass, and `check-contract/SKILL.md` does not exist.

---

### Task 2: Add an executable read-only consumer authority resolver

**Files:**

- Modify: `change-contract/tests/test_contract_state.py`
- Modify: `change-contract/scripts/contract_state.py`

**Interfaces:**

- Extend `verify(root, version=None, allow_missing_ledger=False)` and CLI
  `verify` with `--allow-missing-ledger`. Return `ledger_present` while
  preserving existing keys. Default behavior remains strict.
- Add a read-only CLI:

```text
contract_state.py resolve-consumer \
  --repo <path-within-repository> \
  --branch <full-branch> \
  --ticket <normalized-ticket> \
  [--allow-missing-ledger]
```

It resolves the canonical repository root with
`git rev-parse --show-toplevel`, applies the protocol sanitizer/two-root rules,
and returns sorted JSON containing state, repository root, branch directory,
selected root, active/approval version, contract/approval/ledger paths,
contract SHA, approval-file SHA, current-pointer SHA, approval base SHA, full
HEAD SHA, identity, ancestry result, and ledger presence. True absence returns
`{"state": "absent", ...}`; invalid or ambiguous authority exits nonzero
without writes.

- [ ] **Write RED tests**

Use temporary real Git repositories and prove:

- canonical root is independent of invocation cwd/nested `--repo`;
- the exact branch sanitizer rejects unsafe values;
- one pointer in `.notes` or `ai_docs` selects that root;
- pointers in both roots fail;
- no pointer plus published `vN/` in either root fails as orphaned;
- hidden staging alone is ignored;
- true absence returns `state: absent` without creating/requesting state;
- malformed `current.json`, missing contract/approval, SHA mismatch, approval
  version/branch/ticket mismatch, and non-ancestor base fail;
- full HEAD/base and successful ancestry are returned;
- default verification rejects a missing ledger while the flag verifies
  contract/approval and reports it absent without creating it;
- a present ledger reports true; and
- all success/failure cases preserve complete pre/post file inventories/hashes.

```bash
python -m unittest change-contract.tests.test_contract_state -v
```

Expected before implementation: resolver and new option/flag assertions fail.

- [ ] **Implement the smallest option and verify GREEN**

Implement pure sanitizer/root-selection helpers inside the existing script and
reuse its approval/hash verification; do not duplicate verification in the
skill. Only ledger presence becomes conditional. Preserve active-version,
approval, SHA-256, sorted JSON, immutable approval, and default-call behavior.
The helper must use argument-vector subprocess calls, not shell interpolation.

```bash
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
python -m unittest check-contract/tests/test_eval_contract.py -v
python change-contract/scripts/contract_state.py resolve-consumer --help
git diff --check
```

- [ ] **Independent review and commit**

Review protocol equivalence, canonical-root anchoring, backward compatibility,
zero writes, failure strictness, result shape, command safety, and foreign-cwd
portability.

```bash
git add change-contract/scripts/contract_state.py \
  change-contract/tests/test_contract_state.py
git commit -m "feat: resolve contract consumer authority"
```

**Complete when:** executable tests cover true absence, both valid roots,
ambiguity, orphaning, hash, identity, ancestry, and optional ledger behavior
without weakening any existing immutable contract gate.

---

### Task 3: Add the shared vocabulary and minimal code-first skill

**Files:**

- Create: `check-contract/tests/test_skill_contract.py`
- Modify: `change-contract/references/contract-protocol.md`
- Create after RED: `check-contract/SKILL.md`

- [ ] **Write structural RED before product instructions**

Tests must require:

- explicit user-invoked frontmatter;
- full sibling protocol read before invoking authority resolution;
- absolute sibling helper with
  `resolve-consumer --allow-missing-ledger`;
- canonical repository root, both roots, ambiguity/orphan hard stops, and
  true-absence handling;
- active/approval version, branch, ticket, hash, full base/HEAD, and ancestry;
- a second authority resolution plus equality check is ordered immediately
  before atomic report replacement;
- code/diff analysis text ordered before ledger/summary text;
- every clause family and both audit axes;
- exact check vocabulary/routing sourced from the protocol;
- only report replacement; no fixes/posts;
- authority failure and freshness mismatch preserve an existing report;
- six ordered steps with six completion criteria; and
- `SKILL.md` at most 900 words.

```bash
python -m unittest check-contract/tests/test_skill_contract.py -v
```

Expected: FAIL because the skill/vocabulary are absent.

- [ ] **Add one protocol-owned check vocabulary**

Define:

```text
Clause status: MET | UNMET | EXCEEDED | INDETERMINATE
Ledger status: VERIFIED | QUESTIONABLE | CONTRADICTED

Contract fidelity: PASS | PARTIAL | FAIL
YAGNI:              PASS | WARNING | FAIL
Reuse:              PASS | WARNING | FAIL
Documented drift:   NONE | ACCEPTED | QUESTIONABLE
Undocumented drift: NONE | PRESENT

Overall verdict: PASS | PASS WITH DOCUMENTED DRIFT |
                 NEEDS HUMAN REVIEW | CONTRACT VIOLATED
Recommended next skill: <ordered route>
```

Aggregation:

- Contract fidelity owns Outcome, B/N/I/C clauses, and whether each B's
  acceptance evidence actually demonstrates the behavior. Reuse clauses,
  expected surface, and complexity budget still receive clause statuses, but
  aggregate into Reuse, YAGNI, and drift—not fidelity. This makes a behaviorally
  correct implementation with an unexpected helper/surface a fidelity PASS
  while honestly reporting simplicity/drift.
- `Contract fidelity FAIL`: any Outcome/B/N/I/C is UNMET, or EXCEEDED in a way
  that changes an approved behavior/public contract/risk boundary.
- `Contract fidelity PARTIAL`: no FAIL condition, but any fidelity-owned clause
  or mapped acceptance proof is INDETERMINATE.
- `Contract fidelity PASS`: every fidelity-owned clause is determinate and
  satisfied.
- `YAGNI FAIL`: any proven unearned item adds a module, runtime dependency,
  configuration, public interface, violates a numeric complexity budget of
  zero, or two or more localized unearned layers/wrappers/branches exist.
- `YAGNI WARNING`: exactly one localized item is plausibly unearned but does
  not violate an explicit zero budget; `PASS`: no proven/questionable item.
- `Reuse FAIL`: a compatible current helper/component/service/platform feature
  is demonstrably duplicated or bypassed; `WARNING`: compatibility remains
  indeterminate or only a near-duplicate exists; `PASS`: every changed
  responsibility has an evidenced reuse/no-reuse verdict.
- `Documented drift NONE`: zero D entries; `ACCEPTED`: every D entry is
  VERIFIED and bounded; `QUESTIONABLE`: any D entry is QUESTIONABLE,
  CONTRADICTED, incomplete, or actually contract-changing.
- `Undocumented drift PRESENT`: any implementation-path, expected-surface, or
  complexity-budget deviation lacks a matching accepted D entry; otherwise
  `NONE`.

Use the design's exact routing:

| Finding | Route |
|---|---|
| Missing/incorrect behavior | `exec-ticket` |
| Correct behavior plus duplication/bloat/missed reuse | `clean-up` |
| Correctness and simplicity | `exec-ticket`, then `clean-up` |
| Contract obsolete/wrong | `change-contract` for a new human-approved version |
| Contract satisfied and lean | `qa-ticket` |
| Acceptance QA exists and review evidence is needed | `qa-pr` |

Apply this exhaustive precedence after authority succeeds:

| Order | Observable condition | Overall verdict | Route |
|---:|---|---|---|
| 1 | Approved contract is demonstrably obsolete/wrong because current human/product authority or repository constraints conflict with it | `CONTRACT VIOLATED` | `change-contract` |
| 2 | Fidelity `FAIL`; contract remains the authority; YAGNI/Reuse also has findings | `CONTRACT VIOLATED` | `exec-ticket`, then `clean-up` |
| 3 | Fidelity `FAIL`; contract remains the authority; no simplicity finding | `CONTRACT VIOLATED` | `exec-ticket` |
| 4 | Fidelity `PARTIAL`, documented drift `QUESTIONABLE`, or undocumented drift `PRESENT`, with a YAGNI/Reuse finding | `NEEDS HUMAN REVIEW` | `clean-up`; cite the human-review precondition |
| 5 | Fidelity `PARTIAL` or unresolved drift without a code correction finding | `NEEDS HUMAN REVIEW` | `qa-ticket`; cite the evidence/human-review precondition |
| 6 | Fidelity `PASS` and YAGNI/Reuse is `WARNING` or `FAIL` | `NEEDS HUMAN REVIEW` | `clean-up` |
| 7 | All three axes pass, documented drift `ACCEPTED`, undocumented drift `NONE` | `PASS WITH DOCUMENTED DRIFT` | `qa-pr` if acceptance QA already exists, otherwise `qa-ticket` |
| 8 | All three axes pass and both drift fields are `NONE` | `PASS` | `qa-pr` if acceptance QA already exists, otherwise `qa-ticket` |

An implementation differing from the approved contract is implementation-wrong
unless there is explicit current authority proving the contract obsolete.
Implementer summaries, code shape, or tests written after the contract are not
such authority.

Generate stable IDs before aggregation:

- `O1` for Outcome;
- preserve authored `B*`, `N*`, `I*`, `C*`, and `R*`;
- `S1..Sn` for expected-surface bullets in contract order;
- `K-MODULES`, `K-DEPENDENCIES`, `K-ABSTRACTIONS`, `K-CONFIGURATION`, and
  `K-PUBLIC-INTERFACES` for complexity budget rows;
- `A-<B-id>` for each acceptance mapping;
- preserve `D1..Dn` ledger order;
- `U1..Un` for undocumented deviations sorted by first file path, then line,
  then description; and
- `F1..Fn` for findings sorted by verdict precedence, then clause/deviation ID,
  then file/line.

The route cites stable F/U/D IDs.

- [ ] **Write six ordered skill steps**

1. **Resolve and verify authority:** resolve ticket/full branch; read sibling
   protocol; invoke `resolve-consumer` using a path inside the target repository;
   require its canonical `git rev-parse --show-toplevel` root and verified
   two-root/identity/hash/ancestry result; record full base/HEAD, active
   version, approval/contract hashes, and worktree state; hard-stop absent or
   failed authority without reading implementation narrative or replacing a
   report.
2. **Derive code-as-shipped first:** inventory exact
   `base..<HEAD>` with renames; separate contract artifacts from implementation;
   read changed source/tests and enough surrounding code; account for public
   contracts, side effects, persisted state, and integrations with `file:line`
   evidence; do not read ledger/report/summary/PR narrative yet.
3. **Classify contract fidelity:** classify Outcome and every
   B/N/I/C/R/surface/budget/evidence clause with the four statuses.
4. **Audit YAGNI and reuse:** search current code for existing
   helpers/components/services/platform features; judge every new abstraction,
   dependency, configuration, layer/wrapper, defensive branch, touched
   responsibility, duplicate, and implementation-coupled test as earned or
   unearned. Correctness requirements are not bloat.
5. **Reconcile ledger and narrative:** only now read ledger and supplied
   summary/PR claims; missing means empty; verify each D entry; classify all
   deviations documented/undocumented; compare claims with the code-first
   account.
6. **Replace report and route:** render fully outside the repository; immediately
   rerun `resolve-consumer` and require unchanged canonical root, HEAD, active
   version, approval bytes/hash, contract hash, base, identity, and ancestry;
   recheck guarded source/contract/ledger/status hashes; atomically
   create/replace only the still-active `check-report.md`; verify no other
   audit-caused final delta; emit the exact verdict/route, and stop. Any
   freshness mismatch aborts and preserves the previous report.

Each step ends with `**Complete when:**`.

- [ ] **Require the report shape**

```markdown
# Contract Check: <ticket> — v<version>

Audit range: <full-base>..<full-head>
Worktree state: <clean or limitation>
Contract SHA-256: <digest>

## Code-first observed behavior
## Clause-by-clause fidelity
## YAGNI and reuse
## Drift reconciliation
## Ordered findings
## Verdict and route
<exact verdict block>
## Mutation attestation
```

Clause rows contain ID/status/evidence/reason. Drift rows contain D/deviation
ID/status/evidence/documentation state. Stable finding IDs are cited by the
route.

- [ ] **Verify GREEN, portability, and compactness**

```bash
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
wc -w check-contract/SKILL.md
git diff --check
```

Smoke from a foreign cwd with active `ai_docs` plus unrelated `.notes`; require
the active lineage is selected and no second lineage/file is created.

- [ ] **Independent spec/quality review and commit**

Review actual text order, single-source vocabulary, missing-ledger behavior,
mutation guard, dirty-state disclosure, routes, portability, and whether any
wording encourages remediation.

```bash
git add check-contract/SKILL.md check-contract/tests/test_skill_contract.py \
  change-contract/references/contract-protocol.md
git commit -m "feat: audit approved change contracts"
```

**Complete when:** structural RED preceded the skill, all suites pass, the
protocol owns vocabulary, and the only authorized mutation is the report.

---

### Task 4: Run treatment evaluations and harden observed failures

**Files:**

- Create during execution, ignored:
  `check-contract-workspace/iteration-2/**`
- Modify only for preserved critical failures, with a failing regression first:
  skill, protocol, or helper.

- [ ] **Create one isolated byte-identical runtime snapshot**

Include only:

```text
check-contract/SKILL.md
change-contract/references/contract-protocol.md
change-contract/scripts/contract_state.py
```

Record file hashes. Do not expose plans, evals, tests, grades, or prior
rollouts.

- [ ] **Run nine fresh treatment trials**

Use the scenario materializer exclusively, verify initial HEAD/status/hashes,
reuse the exact baseline prompt/runner shape with only the isolated skill path
added, and capture rollout/final/timing/tokens/provenance immediately.
Scenario two remains one trial/context per configuration even though the prompt
contains two distinct skill executions against independent targets. Require the
rollout to show execution A ending before execution B starts; A's hard stop ends
only A. Grade both target outcomes and their compound result inside that one
sample. Thus the matrix remains exactly three scenarios × two configurations ×
three trials = 18 accepted samples.

```text
check-contract-workspace/iteration-2/<scenario>/with_skill/trial-<n>/
```

- [ ] **Grade all 18 accepted trials**

Recompute action order, exact range, clause/axis evidence, reuse searches,
ledger verification, verdict/route, initial/final inventories/hashes, and
external/remediation calls. For scenario two, separately require Target A's
root resolution, failed authority gate before implementation/narrative reads,
zero writes, and byte-identical sentinel report. Do not apply valid-audit common
assertions to A. Require Target B's full valid semantic-violation audit and
verify its report contains no A path, SHA, sentinel text, or authority finding.
Persist `target_a_pass`, `target_b_pass`, and `compound_pass`; the sample passes
only when both targets pass. Every treatment sample must pass every applicable
critical assertion.

- [ ] **Aggregate, review, and show the benchmark**

Generate per-scenario/configuration pass rate, mean, population variance,
standard deviation, min/max, duration, tokens, and deltas. Produce
`benchmark.json`, `benchmark.md`, and a static skill-creator viewer with
iteration 1 as the previous workspace. A fresh analyst audits prompt/snapshot
parity, contamination, action order, filesystem evidence, grading, statistics,
variance, false reassurance, and cost. The analyst must disclose that
scenario-two execution B shares context with A and is therefore exposed to
same-context priming; report A, B, and compound rates separately so the compound
scenario is not presented as two independent samples.

- [ ] **Harden only observed failures**

Preserve the failure, add RED regression, apply the smallest general fix, and
rerun all three trials for the affected treatment plus paired baseline in a new
iteration. Never weaken/reorder assertions.

```bash
git commit -am "fix: harden check-contract audits"
```

**Complete when:** 9/9 treatment trials pass every critical assertion and an
independent evaluation reviewer accepts the 18-run causal package.

---

### Task 5: Install and verify handoff

**Files:**

- Modify: `README.md`

- [ ] Add:

```markdown
| `check-contract` | Independently audits shipped code against an approved contract, including YAGNI/reuse, and reports the next skill without fixing |
```

- [ ] Install and verify both runtime links:

```bash
./add check-contract
```

`readlink` and `realpath` must resolve both
`~/.claude/skills/check-contract` and `~/.agents/skills/check-contract` to the
reviewed source.

- [ ] From a foreign cwd, verify both installed copies resolve the installed
  sibling protocol/helper and optional-ledger verification without creating a
  repository file.

- [ ] Run:

```bash
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
files=($(find check-contract/evals change-contract/evals exec-ticket/evals \
  -type f -name '*.json' -not -path '*/.git/*' -print))
jq empty "${files[@]}"
git diff --check
```

- [ ] Obtain an independent install/handoff review and commit:

```bash
git add README.md
git commit -m "docs: add check-contract skill"
```

**Complete when:** runtime links/sibling discovery match source, all suites and
JSON pass, README is accurate, and the tracked worktree is clean.

---

### Task 6: Whole-branch review

- [ ] Generate the base-to-head review package plus SDD ledger, benchmark,
  analyst report, and install evidence.
- [ ] Dispatch a fresh reviewer for spec, instruction quality, immutability,
  two-root resolution, exact diff/code-first order, clause/YAGNI/reuse/drift
  logic, report-only/no-post boundaries, eval causality/reproducibility, and
  runtime handoff.
- [ ] Fix every important finding test-first; rerun affected paired evals for
  behavioral wording changes; re-review.
- [ ] Run final verification:

```bash
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
git diff --check
git status --short --branch
```

**Complete when:** spec, quality, evaluation, immutability, and handoff verdicts
all pass; installed links resolve to final source; the accepted benchmark names
the evaluated source hashes; and `check-contract` is complete before
`diff-brief`.

---

## Final completion gates

- User-invoked frontmatter and six ordered completion gates.
- Single shared vocabulary/resolver and verified immutable authority.
- Exact full base/HEAD and disclosed dirty-state limitations.
- Demonstrable code-first analysis before ledger/author narrative.
- Evidence for every clause, simplicity/reuse issue, ledger entry, and drift.
- Only active `check-report.md` changes; no remediation or external mutation.
- 9/9 treatment trials pass; nine paired baselines remain preserved.
- Benchmark statistics/viewer/analyst review and source hashes exist.
- All three skill suites and installed runtimes are green.
- Whole-branch review is clean.
