# Change Contract Protocol

This file is the single source of truth for contract artifacts, simplicity
rules, and drift classification. Read it whenever creating, executing, or
checking an approved change contract.

## Storage

Derive `<branch-dir>` from the full branch exactly once:

1. `value = re.sub(r"[^A-Za-z0-9._-]+", "-", full_branch)`
2. `value = re.sub(r"-+", "-", value).strip("-")`
3. Preserve ASCII letter case and reject the result when it is empty, `.` or
   `..`.

Sanitize only the directory name; keep the unsanitized full branch in contract
identity. Each approved version lives in `vN/`; `current.json` names the active
version.

Producers and consumers inspect both candidate roots,
`.notes/<branch-dir>/contract/` and `ai_docs/<branch-dir>/contract/`, before
selecting a root or legacy mode:

1. Exactly one `current.json` selects its root for reads and future approvals.
   Continue that root's version lineage even when the other notes directory
   later appears.
2. Pointers in both roots are ambiguous and a hard stop.
3. With no pointer, published/non-staging contract state such as `vN/` in either
   root is partial or orphaned and a hard stop.
4. Only true no-state creation chooses `.notes` when it exists, otherwise
   `ai_docs`. Consumers enter legacy mode for that same no-state result without
   creating or requesting contract state.

Ignore hidden staging artifacts `.vN-*` and `.current.json-*` while resolving;
they neither select a root nor count as published state.

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

Co-located hashes and versioning protect the workflow against accidental,
partial, or contract-only drift. Deliberate coordinated mutation requires an
external trust anchor and is out of scope.

## Drift classification

| Class | Observable condition | Action |
|---|---|---|
| Implementation detail | Required behavior, public contracts, invariants, non-goals, dependencies, and risk envelope remain unchanged | Proceed |
| Bounded deviation | Implementation path or change surface differs while outcome and risk envelope remain intact | Proceed and append an evidence-backed ledger entry |
| Contract deviation | Required behavior, non-goals, public API, data schema, auth/security, billing, destructive effects, user-visible semantics, runtime dependencies, deployment requirements, or promised verification changes | Stop for human approval of a new version |

Classify by contract impact, never diff size.

Read-only inspection, commands, and tests may discover and prove drift. For a
bounded deviation, append the verified entry before an implementation or source
path relies on it—not before discovery. For a contract deviation, stop before
writing tests or source that encode the changed agreement; existing and
read-only tests remain allowed, and the deviation never enters the ledger.

## Execution ledger

Record each bounded deviation with this exact shape:

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

Numbers are strictly monotonic within one version. Evidence cites a `file:line`
anchor or command evidence with its observed result. Append the complete entry
before the affected implementation path is used.

The parent agent is the only writer. Workers treat the contract, approval, and
ledger as read-only, return proposed entries, and let the parent independently
verify their evidence and append accepted entries serially.

## Contract check vocabulary

This protocol is the single source of truth for check vocabulary, aggregation,
precedence, routes, and stable IDs.

Clause status: `MET | UNMET | EXCEEDED | INDETERMINATE`

Ledger status: `VERIFIED | QUESTIONABLE | CONTRADICTED`

Contract fidelity: `PASS | PARTIAL | FAIL`

YAGNI: `PASS | WARNING | FAIL`

Reuse: `PASS | WARNING | FAIL`

Documented drift: `NONE | ACCEPTED | QUESTIONABLE`

Undocumented drift: `NONE | PRESENT`

Overall verdict: `PASS | PASS WITH DOCUMENTED DRIFT | NEEDS HUMAN REVIEW | CONTRACT VIOLATED`

Recommended next skill: `<ordered route>`

### Status semantics

Assign one clause status per stable clause ID:

- Judge each clause's exact approved predicate; do not substitute a broader or
  narrower implementation proxy. Implementation path, expected surface, reuse,
  simplicity, and complexity-budget facts do not alter an Outcome/B clause
  status unless they change its approved behavior, public contract, or risk
  boundary; they aggregate through dedicated axes.
- For positive clauses (O/B/I/C/R/A), `MET` means Git-object or acceptance
  evidence proves the approved predicate; `UNMET` means determinate evidence
  proves it false or missing; `EXCEEDED` means it is met but shipped behavior,
  contract, risk, or responsibility goes beyond its approved boundary.
- Emit one explicit `A-<B-id>` row for every B. `MET` requires that evidence
  demonstrates the exact mapped B predicate. An adjacent behavior, happy path,
  or non-boundary example does not prove it; missing or non-demonstrative
  evidence is `INDETERMINATE`.
- For non-goals (N), `MET` means the excluded behavior is absent; `UNMET` means
  it is present; `EXCEEDED` requires evidence that the implementation actively
  imposes an additional restriction on existing or approved behavior; ordinary
  non-implementation or absence of arbitrary unrequested behavior is `MET`, not
  `EXCEEDED`.
- Negative C predicates such as `C1: None` use the non-goal absence semantics:
  `MET` when the declared-absent contract or side effect is absent and `UNMET`
  when it is present.
- For expected-surface clauses (S), `MET` means the responsibility shipped in
  the predicted surface; `UNMET` means the responsibility did not ship
  anywhere; `EXCEEDED` means it shipped through additional or different paths
  or responsibilities.
- For complexity-budget clauses (K), `MET` means actual count and named items
  are within the cap (using less is `MET`); `UNMET` means an explicitly
  required named item is absent and its present requirement is unsatisfied;
  `EXCEEDED` means the count exceeds the cap or an unapproved item appears in
  that category.
- Family-specific rules take precedence over the general absence rule. N
  clauses and negative C predicates such as `C1: None` cannot be inverted by
  that general rule.
- `INDETERMINATE` means available evidence cannot establish the applicable
  predicate, path, item, or count. Missing, unreadable, or conflicting evidence
  is indeterminate. Proven absence is `UNMET` only for a required positive
  predicate or required item.

Assign ledger status independently:

- Verify D status from complete factual fields, commit chronology, and
  replay-probe evidence. A compatible helper that exists before the affected
  implementation commit qualifies as pre-existing, even when created by the
  same author or created after contract approval. Motive or authorship
  speculation alone cannot make a D entry `CONTRADICTED`.
- `VERIFIED` means every required D field is complete and Git-object or command
  evidence confirms its affected clauses, discovered fact, actual approach,
  timing, and bounded classification.
- `QUESTIONABLE` means the entry is not disproved, but a required field,
  evidence, timing, affected clause, or bounded classification is incomplete
  or ambiguous.
- `CONTRADICTED` means repository evidence falsifies a material claim or the
  entry describes a contract-changing rather than bounded deviation.

### Aggregation

Contract fidelity owns Outcome, B/N/I/C clauses, and whether each B's
acceptance evidence actually demonstrates the behavior. Reuse clauses,
expected surface, and complexity budget still receive clause statuses, but
aggregate into Reuse, YAGNI, and drift—not fidelity. Thus a behaviorally correct
implementation with an unexpected helper or surface remains a fidelity `PASS`
while simplicity and drift remain visible.

- Contract fidelity `FAIL`: any Outcome/B/N/I/C is `UNMET`, or `EXCEEDED` in a
  way that changes an approved behavior, public contract, or risk boundary.
- A fidelity-owned `EXCEEDED` that does not change an approved behavior, public
  contract, or risk boundary is determinate and satisfied for fidelity; its
  consequences still aggregate into YAGNI, Reuse, and drift where applicable.
- Contract fidelity `PARTIAL`: no `FAIL` condition, but any fidelity-owned
  clause or mapped acceptance proof is `INDETERMINATE`.
- Contract fidelity `PASS`: every fidelity-owned clause is determinate and
  satisfied.
- YAGNI requires an evidenced unearned added construct. Correctness defects,
  missing tests, deletions, unexpected surface, and complexity-budget excess
  alone do not establish YAGNI. A budget excess affects YAGNI only when the
  added construct is proven unearned.
- YAGNI `FAIL`: any proven unearned item adds a module, runtime dependency,
  configuration, or public interface, or two or more localized items are
  proven unearned.
- YAGNI `WARNING`: no `FAIL` condition exists, and either exactly one localized
  item is proven unearned or one or more questionable localized items (or any
  other questionable item) exist. YAGNI `PASS`: no proven or questionable item
  exists.
- Every changed responsibility needs recorded full-HEAD full-tree search
  evidence before Reuse can be `PASS`; missing search evidence cannot yield
  `PASS`.
- Reuse `FAIL`: a compatible current helper, component, service, or platform
  feature is demonstrably duplicated or bypassed. Reuse `WARNING`:
  compatibility remains indeterminate or only a near-duplicate exists. Reuse
  `PASS`: every changed responsibility has an evidenced reuse/no-reuse verdict.
- Documented drift `NONE`: zero D entries. Documented drift `ACCEPTED`: every D
  entry is `VERIFIED` and bounded. Documented drift `QUESTIONABLE`: any D entry
  is `QUESTIONABLE`, `CONTRADICTED`, incomplete, or actually contract-changing.
- Undocumented drift `PRESENT`: any implementation-path, expected-surface, or
  complexity-budget deviation lacks a matching accepted D entry. Otherwise it
  is `NONE`.

An implementation differing from the approved contract is
implementation-wrong unless explicit current authority proves the contract
obsolete. Implementer summaries, code shape, or tests written after the
contract are not such authority.

### Routing

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

### Stable IDs

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

The route cites every applicable stable F/U/D ID when present; when no F/U/D
IDs exist, state `IDs: none`.
