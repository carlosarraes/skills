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

### 1. Platform + ticket ID
Parse the optional platform argument (`linear` default, `jira`). Extract the ticket ID from the branch:
```bash
git rev-parse --abbrev-ref HEAD
```
Match `[a-zA-Z]{2,5}-\d+` (case-insensitive) and uppercase it (e.g. `ABC-123`). If none is found and none was given, ask the user for it.

### 2. Land on a feature branch
If on a base branch (`main` / `master` / `develop`), create one: `git checkout -b feature/<ticket-id>-<short-desc>`. If already on a feature branch, stay on it.

### 3. Load the plan
Use the approach already agreed in this session (the grill-me'd plan). If a written plan exists (a `writing-plans` doc, or `ai_docs/<branch>/` / `.notes/<branch>/`), use that. If there is **no** plan and no prior design in the session, you are at the wrong step: point the user to `prep-ticket → brainstorm → grill-me` first — or, for a genuinely trivial ticket, confirm a one-line approach before writing any code.

### 4. Build it test-first
Work the plan **one behavior at a time** via superpowers:test-driven-development:
- **RED** — write a test that pins the required behavior; run it; confirm it fails for the right reason.
- **GREEN** — the laziest code that passes (see the green step above).
- **REFACTOR** — only with tests green; keep the diff minimal.

Repeat until the plan's behaviors are covered.

### 5. Verify and report
Run the full test suite (discover the command from CLAUDE.md / README / `package.json` / Makefile). **All green is the bar.** Then report, in chat:
- Ticket and branch
- Behaviors implemented, with the test that pins each
- Files changed
- Suite result

Then **stop** — exec-ticket ends at green. On a bigger ticket the user runs `/qa-ticket`, `/clean-up`, or `/pr-sweep` next; this skill does not chain to them.

## Edge cases

- **No ticket ID in branch and none given**: ask the user for it.
- **No plan and no prior design in the session**: don't freelance a large design — point to `prep-ticket → brainstorm → grill-me`, or confirm a one-line approach for a trivial ticket, then proceed test-first.
- **No test framework / tests can't run**: discover the runner first. If there genuinely is none, set up the minimal one for the touched code; if that's out of scope, say so explicitly and stop rather than shipping untested code.
- **A step seems untestable** (pure config/wiring): write the thinnest real check you can, or note why it can't be tested — don't use it as a blanket excuse to skip RED.
- **The plan turns out wrong mid-build**: stop and kick back to grill-me / brainstorm; don't paper over a broken design with code.
- **Not in a git repo**: report and stop.
- **Platform CLI / Jira CLI unavailable**: the plan already carries the intent — proceed from it and note the CLI gap.
- **Trivial ticket**: still test-first — just one test and a few lines.
