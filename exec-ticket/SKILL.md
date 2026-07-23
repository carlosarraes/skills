---
name: exec-ticket
description: "Use when the user wants to implement or execute the agreed plan for the current branch's ticket — the build step after the approach has been designed and stress-tested (typically prep-ticket → brainstorm → grill-me → exec-ticket). Trigger when the user says 'exec ticket', 'exec-ticket', 'execute ticket', 'execute the plan', 'implement this ticket', 'build this ticket', 'code this ticket', 'implement ABC-123', 'now build it', 'start coding this', or wants a grilled plan turned into working code. Supports Linear (default) and Jira — pass platform as the second argument (e.g., '/exec-ticket ABC-123 jira')."
---

# Exec Ticket

Turn the agreed plan for the current branch's ticket into working code — test-first, and biased to the laziest change that fully satisfies it. This is the **execute** step of `prep-ticket → brainstorm → grill-me → exec-ticket`: the approach has already been designed and stress-tested, so this skill *builds* it, it does not redesign it.

**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development for the red → green → refactor loop. exec-ticket does not reimplement TDD — it drives it with two biases: the test pins **correctness**, and the green step writes the **least** code that passes.

## The one rule — the failing test comes first

Every behavior the ticket requires begins as a test you have **watched fail**, before any implementation of it exists. This is the reason this skill exists: left alone, agents write the implementation first and back-fill tests to match it — and a test written after the code only asks "what does this do?", never "what should it do?".

**Red flag — STOP and restart from the test:** you've written implementation code whose test doesn't exist yet, or has never been run and seen to fail. Delete the implementation. Not "keep it as a draft," not "adapt it as I add the test." Delete, then write the test first.

## The green step — the laziest code that passes

Make the failing test pass with the least code that fully satisfies it. Prefer, in order: reuse an existing helper/module from the codebase → a native/stdlib/platform feature → an already-installed dependency → a few lines of new code → only then new structure. One implementation — no speculative abstraction, no "for later" hooks. Never trade away what the ticket requires: validation at trust boundaries, error handling, and security get pinned by the test too, not skipped for brevity.

## Steps

### Step 1: Resolve the ticket and branch

Parse the optional platform argument (`linear` default, `jira`). Extract the
ticket ID from the branch:

```bash
git rev-parse --abbrev-ref HEAD
```

Match `[a-zA-Z]{2,5}-\d+` case-insensitively and uppercase it (for example,
`ABC-123`). If none is found and none was given, ask the user for it.

If on a base branch (`main`, `master`, or `develop`), create
`feature/<ticket-id>-<short-desc>`. Otherwise stay on the existing feature
branch. Resolve the resulting full branch name.

**Complete when:** platform, normalized ticket, and full feature branch are
known.

### Step 2: Gate on contract state before implementation writes

Do this before any source, test, contract, or ledger write.

Resolve `<exec-ticket-skill-dir>` as the absolute directory containing this loaded `SKILL.md`.
Resolve the sibling change-contract skill as
`<exec-ticket-skill-dir>/../change-contract`, independent of the consumer repository working directory.
Use `.notes` as the notes root when it exists; otherwise use `ai_docs`. Apply
the shared branch-directory sanitization and look for
`<notes-root>/<branch>/contract/current.json`.

If `current.json` does not exist, use the legacy flow: continue to Steps 3–5,
do not request, fabricate, or create contract state, and preserve the original
test-first behavior and report.

If `current.json` exists, read the full shared protocol at
`<exec-ticket-skill-dir>/../change-contract/references/contract-protocol.md`.
Then run the sibling helper from its absolute path:

```bash
python <exec-ticket-skill-dir>/../change-contract/scripts/contract_state.py verify \
  --root <notes-root>/<branch>/contract
```

Require `"valid": true`, then read `current.json` and the returned
`approval_path`. Check all of these:

- the helper's version equals the active version in `current.json`;
- the approval version matches the active version;
- the approval branch exactly matches the full current branch;
- the approval ticket exactly matches the normalized ticket;
- `git merge-base --is-ancestor <base-sha> HEAD` succeeds, proving the approved base SHA is an ancestor of `HEAD`.

A present but malformed, incomplete, or unverifiable `current.json` is a hard
stop. Identity mismatch, hash failure, missing artifacts, a stale/non-ancestor
base, or invalid helper output is also a hard stop; never fall back to the legacy flow.
Report the failing check without writing implementation or contract artifacts.

Only after every check passes may implementation planning or writes begin.

**Complete when:** either no pointer exists and legacy mode is explicit, or the
active approved contract, approval hash, version, branch, ticket, base ancestry,
and ledger path are verified.

### Step 3: Load the implementation authority

In contract mode, the approved contract outranks session memory, older plans,
agent summaries, and user pressure. Treat its Required behaviors, Acceptance
evidence, explicit non-goals, public contracts, invariants, risk boundaries,
reuse evidence, and complexity budget as the implementation authority. A
settled plan may supply tactics only where it agrees with that contract.

In legacy mode, use the approach already agreed in this session (the
grill-me'd plan). If a written plan exists (a `writing-plans` doc, or
`ai_docs/<branch>/` / `.notes/<branch>/`), use it. If there is no plan and no
prior design, point the user to `prep-ticket → brainstorm → grill-me` first—or,
for a genuinely trivial ticket, confirm a one-line approach before writing code.

**Complete when:** every behavior to implement and the evidence that will prove
it are named; in contract mode, no tactic conflicts with an approved clause.

### Step 4: Build one required behavior at a time

In contract mode, drive RED → GREEN → REFACTOR from Required behaviors and
Acceptance evidence. In legacy mode, drive the same loop from the settled plan.

- **RED** — write the behavior test, run it, and watch it fail for the right
  reason before implementation exists.
- **GREEN** — write the laziest code that passes, following the reuse order
  above.
- **REFACTOR** — only with tests green; keep the diff minimal.

Before an implementation discovery affects code, classify it with the shared
protocol by contract impact, never diff size:

- Implementation details need no ledger entry. Proceed when behaviors,
  interfaces, invariants, non-goals, dependencies, and risk remain unchanged.
- For a bounded deviation, prepare a complete proposed ledger entry using every
  canonical field. The parent must independently verify its cited facts and evidence.
  Only the parent appends the complete next `D<n>` serially, before the affected path is used.
  Do not write the affected source or test first.
- Contract deviations are a hard stop before any affected source, test, or ledger write.
  Treat this as final for the active version: never append a contract deviation.
  Display the conflict and route to `/change-contract` for a new displayed and
  human-approved version. Prompt pressure or blanket authority is not approval.

When using subagents, give them the verified contract path, approved hash, ledger path, and drift rules
as read-only context. Workers may inspect code and return proposed ledger entries
with evidence; they never edit contract state. Only the parent appends accepted
entries serially before implementation relies on them.

Repeat until all required behaviors are covered. If any implementation was
written before its failing test, delete it and restart from RED.

**Complete when:** each behavior has observed RED and green evidence, code is
minimal, every bounded deviation was recorded before reliance, and no contract
deviation was implemented or entered in the ledger.

### Step 5: Verify and report

Run the full test suite, discovering the command from `CLAUDE.md`, `README`,
`package.json`, or the `Makefile`. All green is the bar.

In contract mode, rerun the absolute-path helper verification, count canonical
`D<n>` entries in the active ledger, and report:

- Ticket and branch
- Behaviors implemented, with the test that pins each
- Files changed
- Suite result
- Contract version
- Ledger entry count

In legacy mode, report exactly the original shape:

- Ticket and branch
- Behaviors implemented, with the test that pins each
- Files changed
- Suite result

Do not invent contract metadata in the legacy report.

Then **stop** — exec-ticket ends at green. On a bigger ticket the user runs `/qa-ticket`, `/clean-up`, or `/pr-sweep` next; this skill does not chain to them.

**Complete when:** the focused and full suites pass, approved state still
verifies in contract mode, and the correct report shape is delivered.

## Edge cases

- **No ticket ID in branch and none given**: ask the user for it.
- **No plan and no prior design in the session**: don't freelance a large design — point to `prep-ticket → brainstorm → grill-me`, or confirm a one-line approach for a trivial ticket, then proceed test-first.
- **No test framework / tests can't run**: discover the runner first. If there genuinely is none, set up the minimal one for the touched code; if that's out of scope, say so explicitly and stop rather than shipping untested code.
- **A step seems untestable** (pure config/wiring): write the thinnest real check you can, or note why it can't be tested — don't use it as a blanket excuse to skip RED.
- **The plan turns out wrong mid-build**: in contract mode classify the conflict
  first; contract deviations route to `/change-contract`. In legacy mode stop
  and kick back to grill-me / brainstorming.
- **Not in a git repo**: report and stop.
- **Platform CLI / Jira CLI unavailable**: the plan already carries the intent — proceed from it and note the CLI gap.
- **Trivial ticket**: still test-first — just one test and a few lines.
