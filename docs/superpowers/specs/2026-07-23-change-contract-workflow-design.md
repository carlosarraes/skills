# Change Contract Workflow Design

Date: 2026-07-23
Status: proposed

## Purpose

Agent-written code creates two separate review problems:

1. Before implementation, the human needs a compact agreement about what the
   change should become.
2. After implementation, the human needs an independent account of what the code
   actually became.

The workflow closes that loop without freezing implementation tactics:

```text
prep-ticket
  -> brainstorm + grill
  -> change-contract
  -> human approval
  -> exec-ticket
  -> check-contract
  -> routed next step
```

`diff-brief` serves the contractless case, especially PRs written by somebody
else. `explain-diff` remains the deeper teaching tool for selected areas.

## Goals

- Make the intended behavior, non-goals, risk envelope, and evidence explicit
  before implementation.
- Preserve the human-approved baseline while allowing agents to discover a
  better implementation path.
- Let implementers proceed through bounded drift and record why.
- Stop only when a discovery changes the approved outcome or risk envelope.
- Independently compare expected behavior with code-as-shipped.
- Treat YAGNI and reuse as auditable requirements, not aesthetic suggestions.
- Route findings to the focused skill that owns remediation.
- Orient a reviewer quickly inside any existing PR, even when no contract exists.

## Non-goals

- Replacing ticket preparation, design, grilling, TDD, QA, or code review.
- Making `check-contract` edit code or approve its own remediation.
- Treating predicted files or line counts as hard implementation constraints.
- Declaring code "safe" based on an agent-generated risk label.
- Turning `explain-diff` into a correctness-review skill.
- Posting comments to a PR without an explicit request.

## Skill boundaries and invocation

All three new skills are user-invoked. They use
`disable-model-invocation: true`, because each represents a deliberate human
checkpoint and none needs autonomous triggering.

| Skill | Leading word | Job |
|---|---|---|
| `change-contract` | contract | Create and approve the immutable expected change |
| `check-contract` | audit | Compare shipped code with the contract, assess simplicity, and route |
| `diff-brief` | briefing | Orient a reviewer inside a contractless PR, branch, or commit |

Existing skills retain their boundaries:

- `prep-ticket` gathers context and proposes the laziest starting approach.
- Brainstorming and grilling settle design decisions.
- `exec-ticket` implements test-first and records bounded deviations when an
  approved contract exists.
- `clean-up` fixes valid simplicity, reuse, and quality findings.
- `qa-ticket` and `qa-pr` prove behavior.
- `explain-diff` teaches selected code deeply.

## Single source of truth

The contract schema, drift classification, integrity rules, and verdict vocabulary
live in one disclosed reference:

`change-contract/references/contract-protocol.md`

`change-contract`, `exec-ticket`, and `check-contract` point to that reference
when a contract is present. Their `SKILL.md` files contain only their ordered
steps, completion criteria, and branch-specific behavior.

## Artifact layout

Use the repository's existing notes convention:

```text
<notes-root>/<branch>/contract/
  current.json
  v1/
    contract.md
    approval.json
    execution-ledger.md
    check-report.md
  v2/
    ...
```

`<notes-root>` is `.notes` when that directory exists, otherwise `ai_docs`.
`current.json` names the active approved version. A new agreement creates a new
version directory; prior baselines and ledgers remain unchanged.

### `contract.md`

The human-approved baseline for one version:

- identity: ticket, branch, base commit, creation time
- outcome: one-sentence postcondition
- required behaviors
- explicit non-goals
- invariants and risk boundaries
- expected public contracts and side effects
- reuse candidates with file anchors
- expected change surface
- complexity budget
- acceptance evidence mapped to each required behavior
- unresolved decisions, which must be empty before approval

The complexity budget predicts new modules, dependencies, abstractions,
configuration, and public interfaces. It is an attention signal, not a
line-count gate. A deviation from it requires evidence; it does not automatically
fail the implementation.

### `approval.json`

Approval freezes the baseline by recording:

- contract version
- approving human
- approval timestamp
- base commit
- SHA-256 of `contract.md`

Every consumer verifies the hash before trusting the contract. The approved
`contract.md` is immutable. A materially changed agreement becomes a new
version directory approved by the human; implementation agents never rewrite an
approved version.

Workflow immutability detects accidental, partial, and contract-only drift and
enforces versioning. Deliberate coordinated mutation of `contract.md` plus
`approval.json` is outside the threat model and requires an external trust
anchor, which is not included here.

Hidden `.vN-*` staging directories and `.current.json-*` pointer temp files
left by hard process death are tolerated and ignored. They never become active
and do not block retry; only `current.json` pointing to a complete, verified
`vN` determines active contract state.

### `execution-ledger.md`

An append-only account of implementation discoveries. Every bounded deviation
records:

- timestamp and agent identity
- affected contract clauses
- discovered fact
- actual approach
- reason for proceeding
- alternatives considered
- risk delta
- verification evidence

Implementation details that remain inside the predicted approach need no entry.
Contract deviations stop for approval. Work resumes against the newly approved
version, so a contract deviation never becomes a silently accepted ledger fact.

### `check-report.md`

The report-only audit result for that version. Re-running `check-contract`
replaces this derived artifact but never changes the contract or ledger.

## Drift model

Classify drift by impact on the approved agreement, not diff size.

| Class | Observable condition | Action |
|---|---|---|
| Implementation detail | Required behavior, public contracts, invariants, non-goals, dependencies, and risk envelope stay unchanged | Proceed |
| Bounded deviation | The implementation path or change surface differs, but the approved outcome and risk envelope remain intact | Proceed and append a ledger entry |
| Contract deviation | Required behavior, non-goals, public API, data schema, auth/security, billing, destructive effects, user-visible semantics, runtime dependencies, deployment requirements, or promised verification changes | Stop for human approval |

The risk-bearing subjects in the final row promote a change to contract deviation
regardless of how few lines it touches.

## `change-contract` design

### Inputs

- The settled design from the current session or a written plan
- Ticket context
- Repository rules
- Relevant code and tests
- Reuse candidates already found by `prep-ticket`, plus a focused confirmation
  scan

### Steps

1. Resolve the ticket, branch, base commit, plan, and notes root.
   Completion: every identity field has a concrete value.
2. Trace the current behavior and reuse surface in real code.
   Completion: every proposed new responsibility has an existing-code reuse
   verdict with file evidence.
3. Draft the contract using the protocol.
   Completion: every required behavior maps to evidence, non-goals are explicit,
   the complexity budget is concrete, and unresolved decisions are listed.
4. Present the draft and wait for explicit human approval.
   Completion: the user approves or edits the draft; silence is not approval.
5. Freeze the approved baseline and initialize an empty ledger.
   Completion: the new version directory exists, `approval.json` matches the
   SHA-256 of `contract.md`, `current.json` names that version, the contract
   contains no unresolved decisions, and the ledger is empty.

The skill ends at approval. It recommends `exec-ticket`; it does not begin
implementation.

### YAGNI contract

The contract encodes the same laziest-first order as `exec-ticket`:

1. existing helper or module
2. native, standard-library, or platform capability
3. already-installed dependency
4. a few lines of new code
5. new structure

Every step skipped in that order needs present-tense evidence. Future flexibility
does not justify current complexity. Security, validation, accessibility, error
handling, and explicitly required behavior remain correctness requirements, not
optional complexity.

## `exec-ticket` integration

`exec-ticket` keeps its current test-first implementation job.

When an approved contract exists:

1. Verify the contract hash before writing code.
2. Use required behaviors and acceptance evidence to drive RED-GREEN-REFACTOR.
3. Classify discoveries using the shared drift model.
4. Proceed through implementation details.
5. Append bounded deviations to the ledger before relying on them.
6. Stop on contract deviation and request a new human-approved contract version.
7. Include the contract version and ledger-entry count in the final report.

When no approved contract exists, `exec-ticket` retains its current behavior. The
new workflow is explicit rather than silently imposed on every ticket.

Subagents receive the contract path, approval hash, ledger path, and drift rules
in their dispatch prompt. Only one writer may append to a ledger at a time; the
parent serializes entries returned by parallel workers.

## `check-contract` design

`check-contract` is read-only with respect to source code, the contract, and the
ledger. It may replace only `check-report.md`.

### Independent audit order

1. Verify contract integrity and resolve the implementation diff.
   Completion: the approved hash matches and the exact base/head range is known.
2. Derive observed behavior from the diff and surrounding code without reading
   the execution ledger or implementer summary.
   Completion: every required behavior and every changed public contract,
   side effect, persisted state, and external integration has an observed-code
   account with file evidence.
3. Compare observed behavior with the approved contract.
   Completion: every contract clause is classified met, unmet, exceeded, or
   indeterminate.
4. Audit YAGNI and reuse against current code.
   Completion: every new abstraction, dependency, configuration surface, and
   duplicated responsibility has an earned-or-unearned verdict with evidence.
5. Read the execution ledger and verify each justification against code.
   Completion: every entry is verified, questionable, or contradicted, and every
   observed deviation is documented or undocumented.
6. Write the report and route the next action.
   Completion: the report contains both audit axes, one overall verdict, ordered
   findings, and a concrete next-skill recommendation.

### Audit axes

**Contract fidelity**

- required behaviors
- non-goals
- interfaces and invariants
- side effects and risk boundaries
- acceptance evidence
- documented and undocumented drift

**Simplicity and reuse**

- missed existing helpers, components, services, or platform features
- duplicated logic
- abstractions without a current requirement or real boundary
- configuration for constants
- unnecessary runtime dependencies
- extra layers, wrappers, defensive branches, or touched files
- tests coupled to implementation instead of behavior

### Verdict and routing

```text
Contract fidelity: PASS | PARTIAL | FAIL
YAGNI:              PASS | WARNING | FAIL
Reuse:              PASS | WARNING | FAIL
Documented drift:   NONE | ACCEPTED | QUESTIONABLE
Undocumented drift: NONE | PRESENT

Overall verdict: PASS | PASS WITH DOCUMENTED DRIFT |
                 NEEDS HUMAN REVIEW | CONTRACT VIOLATED
Recommended next skill: <ordered route>
```

Routing rules:

| Finding | Route |
|---|---|
| Missing or incorrect required behavior | `exec-ticket` |
| Correct behavior with duplication, bloat, or missed reuse | `clean-up` |
| Correctness and simplicity failures | `exec-ticket`, then `clean-up` |
| The approved contract is obsolete or wrong | `change-contract` for a new human-approved version |
| Contract satisfied and implementation lean | `qa-ticket` |
| Acceptance QA already exists and review evidence is needed | `qa-pr` |

The recommendation cites the exact findings the next skill owns. The checker
never fixes them.

## `diff-brief` design

`diff-brief` works without a contract on a PR, branch, commit, or range. Its
leading word is a briefing: fast orientation that allocates human review
attention.

### Analysis order

1. Resolve the exact diff and read changed files plus enough surrounding code.
2. Independently derive code-as-shipped behavior before reading the PR narrative.
3. Group changes by behavior and responsibility rather than file order.
4. Map changed signatures, public contracts, state, side effects, and external
   systems.
5. Search for existing helpers and components that may make new code redundant.
6. Assign low, medium, or high attention with evidence and uncertainty.
7. Select the few hunks a human should read and explain why.
8. Read the PR description and compare claimed with observed behavior.
9. Draft author questions and possible inline comments without posting them.

### Output

The default output is a private Markdown briefing in chat. It writes no source
files and posts nothing externally. When the user explicitly requests a
shareable artifact, the same briefing may be rendered and hosted without
changing its analysis or posting it to the PR.

- PR in one sentence
- behavioral change map
- changed contracts and signatures
- attention map with evidence
- human reading budget
- reuse and duplication questions
- claimed versus observed behavior
- verification evidence present or missing
- draft questions and comments

The report never labels code safe and never substitutes orientation for a
correctness review. It recommends `stamp-check`, `review-swarm`, `clean-up`, or
`explain-diff` when the next job belongs there.

## Error handling

- Missing settled plan: `change-contract` routes back to brainstorming or
  grilling.
- Unresolved contract decision: approval remains blocked.
- Hash mismatch: `exec-ticket` and `check-contract` stop and request human review.
- Missing ledger: treat it as empty and report every observed deviation as
  undocumented.
- Ambiguous diff base: ask once rather than audit a guessed range.
- Incomplete repository context: mark affected findings indeterminate instead of
  inventing behavior.
- Parallel ledger writes: parent agent serializes entries; workers return
  proposed entries as artifacts.

## Verification and benchmark strategy

Skill development follows RED-GREEN-REFACTOR one skill at a time. Each skill is
fully tested and committed before the next is authored.

### `change-contract`

Baseline scenarios test whether an unguided agent:

- converts a plan into vague prose without checkable behaviors
- omits non-goals, reuse evidence, or a complexity budget
- invents speculative abstractions
- proceeds without explicit approval

Success requires a complete contract, evidence-backed reuse scan, explicit
approval gate, and verifiable immutable snapshot.

### `exec-ticket` integration

Pressure scenarios test whether an implementer:

- silently edits the baseline
- stops for harmless implementation details
- proceeds through contract-changing security or data-model drift
- records a self-serving ledger entry without evidence

Success requires correct drift classification, immutable baseline preservation,
and evidence-backed bounded-deviation entries.

### `check-contract`

Baseline scenarios include:

- contract-compliant but over-engineered code
- simple code that violates required behavior
- justified documented drift
- undocumented drift hidden by an implementer summary
- duplicated existing helpers

Success requires independent code-first analysis, separate fidelity/YAGNI/reuse
scores, no source edits, and correct routing.

### `diff-brief`

Baseline scenarios include another author's large PR with:

- a misleading PR description
- one high-attention change in an ordinary-looking file
- duplicated helper logic
- missing verification
- a large number of low-value changed files

Success requires behavior grouping, evidence-backed attention, a small reading
budget, claimed-versus-observed comparison, and unposted review drafts.

Quantitative checks cover required report sections, file evidence, forbidden
"safe" labels, immutable hash validation, source-write absence, drift
classification, and routing. Human review compares usefulness, false reassurance,
and time-to-understanding against the baseline.

## Delivery order

1. Create and verify `change-contract` plus the shared protocol.
2. Verify and update `exec-ticket` to consume approved contracts.
3. Create and verify `check-contract`.
4. Create and verify `diff-brief`.
5. Update `orchestrate`, `README.md`, and focused handoff references.
6. Run an end-to-end benchmark on a historical Acme PR with a reconstructed
   pre-implementation contract, then test `diff-brief` on a PR from another
   author.

This order keeps each skill's post-completion steps out of the current skill's
test cycle and preserves the one-skill-at-a-time deployment gate.
