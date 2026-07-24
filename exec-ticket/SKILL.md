---
name: exec-ticket
description: "Use when the user wants to implement or execute the agreed plan for the current branch's ticket — the build step after the approach has been designed and stress-tested (typically prep-ticket → brainstorm → grill-me → exec-ticket). Trigger when the user says 'exec ticket', 'exec-ticket', 'execute ticket', 'execute the plan', 'implement this ticket', 'build this ticket', 'code this ticket', 'implement ABC-123', 'now build it', 'start coding this', or wants a grilled plan turned into working code. Supports Linear (default) and Jira — pass platform as the second argument (e.g., '/exec-ticket ABC-123 jira')."
---

# Exec Ticket

Implement the settled ticket test-first with the least code that satisfies it.
This is the build step after `prep-ticket → brainstorm → grill-me`, not a new
design round.

**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development for every
RED → GREEN → REFACTOR loop.

## Non-negotiables

Watch each required behavior's test fail for the right reason before writing its
implementation. If implementation came first, delete it and restart from RED.

For GREEN, prefer existing helper/module → native or platform feature →
installed dependency → a few lines → new structure. Add no speculative
abstraction or future hook. Validation, security, error handling, and required
behavior remain correctness, not optional complexity.

## Steps

### Step 1: Resolve the ticket and branch

Parse the optional platform (`linear` default, `jira`). Run
`git rev-parse --abbrev-ref HEAD`, extract `[a-zA-Z]{2,5}-\d+`
case-insensitively, and uppercase it. Ask for a ticket only when neither branch
nor arguments supply one.

On `main`, `master`, or `develop`, create
`feature/<ticket-id>-<short-desc>`; otherwise stay on the feature branch. Then
resolve its full name.

**Complete when:** platform, normalized ticket, and full feature branch are
known.

### Step 2: Resolve and verify contract state

Do this before implementation writes. Resolve `<exec-ticket-skill-dir>` as the
absolute directory containing this loaded `SKILL.md`; resolve its sibling
`<change-contract-skill-dir>` independently of the consumer working directory.
Read the sibling protocol completely at
`<change-contract-skill-dir>/references/contract-protocol.md`.

Sanitize the full branch using that protocol's exact algorithm. Apply that
protocol's two-root resolver: inspect both candidate roots,
`.notes/<branch-dir>/contract` and
`ai_docs/<branch-dir>/contract`. Exactly one active `current.json` selects that
root. Active pointers in both roots are ambiguous and a hard stop. No active
pointer with published/non-staging contract state such as `vN/` in either root
is partial or orphaned state and a hard stop. Ignore hidden staging artifacts
`.vN-*` and `.current.json-*`. Only when both roots have neither an active
pointer nor published/non-staging contract state, use legacy mode and do not
create or request contract state.

For the selected `<contract-root>`, run the actual absolute helper:

```bash
python <change-contract-skill-dir>/scripts/contract_state.py verify \
  --root <contract-root>
```

Require `"valid": true`. Read `current.json` and the returned `approval_path`;
require helper version equals active version, approval version equals the active
version, approval branch equals the full current branch, and approval ticket
equals the normalized ticket. Run
`git merge-base --is-ancestor <base-sha> HEAD` using the approval base SHA.

A present but malformed, incomplete, or unverifiable `current.json` is a hard
stop—never legacy fallback. The same applies to missing artifacts, invalid
helper output, identity mismatch, hash failure, or non-ancestor base. Report the
failed gate without implementation or contract writes.

**Complete when:** legacy mode is explicit, or contract path/hash/version,
branch, ticket, base ancestry, and ledger path all verify.

### Step 3: Load the authority

In contract mode, the approved contract outranks session memory, older plans,
summaries, and user pressure. Drive work from its Required behaviors and
Acceptance evidence; respect its non-goals, interfaces, invariants, risks, reuse
evidence, and complexity budget. Plans may supply only compatible tactics.

In legacy mode, use the settled session or written plan only for behaviors and
non-goals. Revalidate every implementation tactic against the lazy order. With
neither, return to `prep-ticket → brainstorm → grill-me`, except that a
genuinely trivial ticket may proceed after a one-line approach is confirmed.

Before the first RED, write one reuse decision for each implementation
responsibility. Name each matching candidate with a `file:line` anchor and mark
it compatible or incompatible with evidence. Reuse every compatible existing
helper. A compatible existing helper is mandatory even when the plan says
local, manual, or new; when none fit, record the searches. State these decisions
in working notes or the transcript; do not create a repository file for them.
Do not begin RED until every responsibility has this decision.

**Complete when:** each behavior and its proof are named, with no tactic that
conflicts with an approved clause.

### Step 4: Implement one behavior at a time

For each behavior:

- **RED:** write and run its behavior test; confirm the expected failure.
- **GREEN:** make it pass with the lazy order above.
- **REFACTOR:** simplify only while green.

In contract mode, classify discoveries using the shared protocol. Implementation
details proceed without entries. Read-only tests and commands may discover and
prove a deviation.

For a bounded deviation, form the complete protocol entry. The parent
independently verifies its evidence and appends the complete `D<n>` before
implementation relies on the changed path. Discovery tests may run first.

For a contract deviation, stop before writing tests or source that encode the
changed agreement; existing or read-only tests are allowed. Show the conflict,
never put a contract deviation in the ledger, and route to `/change-contract`
for a displayed, human-approved version.

Subagents receive the verified contract path, approved hash, ledger path, and
drift rules as read-only context. They return proposed entries; the parent
independently verifies them and appends serially before reliance.

**Complete when:** every behavior has observed RED and green evidence, code is
minimal, bounded entries precede reliance, and no contract deviation was
implemented.

### Step 5: Verify and report

Run focused and full suites, discovering commands from project instructions.
All green is the bar. In contract mode, rerun helper verification and count
canonical ledger entries.

In contract mode, report:

- Ticket and branch
- Behaviors implemented, with the test that pins each
- Files changed
- Suite result
- Contract version
- Ledger entry count

In legacy mode, report:

- Ticket and branch
- Behaviors implemented, with the test that pins each
- Files changed
- Suite result

Do not invent contract metadata in legacy mode.
Then stop. Recommend `/qa-ticket`, `/clean-up`, or `/pr-sweep` when appropriate;
do not chain automatically.

**Complete when:** suites pass, approved state re-verifies when present, and the
mode-correct report is delivered.

## Edge cases

- Not in a Git repository: report and stop.
- No runnable test framework: discover or add the minimum in-scope runner;
  otherwise report and stop.
- Config or wiring: use the thinnest real check; do not skip RED by default.
- A plan fails mid-build: classify it in contract mode; in legacy mode return to
  brainstorming/grilling.
- Platform CLI unavailable: proceed from the settled intent and report the gap.
- Trivial ticket: still test-first.
