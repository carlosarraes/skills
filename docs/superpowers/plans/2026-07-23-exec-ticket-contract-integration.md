# Exec-ticket Contract Integration Plan

> **For Codex:** Execute this plan with subagent-driven development. Use one
> fresh implementer per task, generate a review package, obtain independent spec
> and quality review, fix findings, and update `.superpowers/sdd/progress.md`.

**Goal:** Make `exec-ticket` consume a valid approved change contract when one
exists, proceed through implementation details and evidence-backed bounded
deviations, stop for contract deviations, and preserve its current behavior in
repositories without contracts.

**Architecture:** `change-contract/references/contract-protocol.md` remains the
single source of truth. `exec-ticket` adds only ordered contract-aware steps and
completion criteria. The parent agent is the sole ledger writer; subagents
receive verified contract context read-only and return proposed deviation
entries. No new production helper is added unless an evaluation demonstrates a
need.

**Threat model:** Workflow integrity detects accidental, partial, contract-only,
wrong-branch, and stale-base consumption. Deliberate coordinated mutation of
the contract and approval metadata remains out of scope.

**Evaluation rule:** Run three independent trials per scenario before and after
the integration. Treatment wrappers must be behavior-neutral: repo path, skill
path, exact prompt, and artifact destinations only. Persist plaintext runner
files before dispatch and record their SHA-256 plus rollout identity so prompt
parity is auditable.

---

### Task 1: Define pressure fixtures and record the current-skill baseline

**Files:**
- Create: `exec-ticket/evals/evals.json`
- Create: `exec-ticket/evals/fixtures/contract-repo/**`
- Create: `exec-ticket/evals/fixtures/legacy-repo/**`
- Create: `exec-ticket/tests/test_eval_contract.py`
- Create during execution, ignored:
  `exec-ticket-workspace/iteration-1/**`

**Steps:**

1. Create a small runnable Python fixture with:
   - branch identity `feature/proj-123`;
   - a settled `plan.md`;
   - `src/checkout.py`, `src/pricing.py`, and focused tests;
   - a valid approved v1 contract whose required behavior rejects percentages
     above 100 and whose expected path uses local validation;
   - an empty ledger;
   - a post-contract existing `validate_percentage` helper plus
     `.worker-results/validation.md` with exact file/test evidence.
2. Create a legacy copy with the same plan/source but no contract artifacts.
3. Add three evals with exact prompts and assertions:
   - `bounded-deviation-under-paperwork-pressure`
   - `contract-deviation-under-small-diff-pressure`
   - `no-contract-legacy-regression`
4. Structural tests must validate JSON shape, unique names, exact critical
   assertions, valid fixture v1 integrity, empty initial ledger, and absence of
   contract state in the legacy fixture.
5. Run three fresh trials per eval using the current `exec-ticket` skill. Each
   trial gets its own copied repository and persisted neutral runner prompt.
6. Grade transcript order and environment outcomes. Record exact
   `task_complete.duration_ms`, final total tokens, rollout/model provenance,
   and sample-specific evidence.
7. Write `baseline-analysis.md`. Expected discrimination:
   - contract verification/classification/ledger behavior fails in the first
     two scenarios;
   - the legacy scenario is a regression control and may pass.
8. Commit:

```bash
git add exec-ticket/evals exec-ticket/tests/test_eval_contract.py
git commit -m "test: define exec-ticket contract pressure scenarios"
```

**Complete when:** nine baseline trials are preserved, every critical contract
assertion has RED evidence, and the fixture/grade schemas pass.

---

### Task 2: Add the minimal contract-aware execution protocol

**Files:**
- Modify: `change-contract/references/contract-protocol.md`
- Modify: `exec-ticket/SKILL.md`
- Create: `exec-ticket/tests/test_contract_integration.py`

**Steps:**

1. Write failing structural tests before editing product instructions. Assert:
   - contract discovery occurs after branch/ticket resolution and before writes;
   - an existing `current.json` requires full protocol read and helper
     verification;
   - malformed/tampered state is a hard stop, never legacy fallback;
   - approval branch, ticket, active version, and base-SHA ancestry are checked;
   - the approved contract outranks session memory and older plans;
   - RED-GREEN-REFACTOR is driven from required behaviors/evidence;
   - implementation details proceed without ledger entries;
   - bounded deviations require complete evidence and a parent append before
     the changed path is used;
   - contract deviations stop before affected source/test writes and never
     become ledger entries;
   - subagents receive path/hash/ledger/drift rules read-only and return proposed
     entries; only the parent appends serially;
   - final reporting includes contract version and ledger count;
   - no `current.json` preserves the existing flow and report.
2. Run the new test and record RED.
3. Add one canonical ledger format to the shared protocol:

```markdown
## D<n> — <ISO-8601 timestamp> — <agent>

- Affected clauses:
- Discovered fact:
- Actual approach:
- Reason for proceeding:
- Alternatives considered:
- Risk delta:
- Verification evidence:
```

   Require monotonic numbering, `file:line` or command evidence, append before
   reliance, and parent-only serialized writes.
4. Refactor `exec-ticket/SKILL.md` into explicit ordered steps with
   `**Complete when:**` criteria while preserving its existing TDD/YAGNI and
   no-contract behavior.
5. Resolve the sibling `change-contract` skill directory independently of the
   consumer repository cwd; use its helper for `verify`.
6. Run all `exec-ticket` and `change-contract` tests, word/hygiene checks, CLI
   smoke, and `git diff --check`.
7. Commit:

```bash
git add \
  exec-ticket/SKILL.md \
  exec-ticket/tests/test_contract_integration.py \
  change-contract/references/contract-protocol.md
git commit -m "feat: execute approved change contracts"
```

**Complete when:** structural tests pass, legacy wording remains present, the
skill is portable from a foreign cwd, and no helper code was added without
observed need.

---

### Task 3: Prove drift classification and ledger ordering

**Files:**
- Create during execution, ignored:
  `exec-ticket-workspace/iteration-2/**`
- Modify only if a critical failure is observed:
  `exec-ticket/SKILL.md`
  `change-contract/references/contract-protocol.md`

**Steps:**

1. Rerun all three evals three times with fresh contexts and the same neutral
   runner shape used by controls.
2. Grade every assertion against both arms.
3. Critical treatment requirements:
   - valid contract verified before any test/source write;
   - bounded discovery independently checked;
   - parent appends exactly one complete ledger entry before source relies on
     the changed path;
   - worker never writes the ledger;
   - existing helper reused and tests pass;
   - semantic clamp classified as contract deviation regardless of diff size;
   - contract-deviation trial changes no source/tests/ledger/approved state and
     routes to `/change-contract`;
   - no-contract trial fabricates no contract state and retains RED-before-GREEN.
4. Aggregate mean/variance, time/tokens, model/rollout provenance, action-order
   grades, and environment hashes into `benchmark.json`/`benchmark.md`.
5. Generate a static review viewer with the baseline as previous workspace.
6. If a critical assertion fails, preserve it, apply the smallest instruction
   fix, add a regression test, and rerun only the affected scenario plus its
   paired control in the next iteration. Do not weaken assertions.
7. Commit only observed hardening:

```bash
git commit -am "fix: harden exec-ticket contract drift handling"
```

**Complete when:** every critical treatment assertion passes in every trial and
an independent reviewer validates prompt parity, grades, action order,
filesystem outcomes, and statistics.

---

### Task 4: Verify installation and handoff

**Files:**
- Modify only if discovery text is inaccurate: `README.md`

**Steps:**

1. Run `./add exec-ticket` and confirm both runtime symlinks resolve to the
   source skill.
2. Run all `exec-ticket` and `change-contract` tests, eval JSON validation,
   helper CLI smoke, foreign-cwd command smoke, and `git diff --check`.
3. Confirm the installed skill loads the sibling protocol/helper successfully.
4. Confirm the worktree is clean. Commit README only if an actual discovery
   correction was required.

**Complete when:** installed runtime behavior matches the reviewed source,
verification is green, and no unearned product change exists.

---

### Task 5: Whole-branch review

Generate a base-to-head review package and dispatch a fresh reviewer. The review
must cover contract discovery, wrong-branch/stale-base rejection, verification
ordering, drift boundaries, ledger append ordering, parent-only serialization,
TDD preservation, legacy compatibility, evaluation integrity, and installation.
Fix every important finding test-first and re-review.

**Complete when:** spec, quality, evaluation, and handoff verdicts all pass.

