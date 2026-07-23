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
