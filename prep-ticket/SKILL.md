---
name: prep-ticket
description: Use when preparing to implement a Linear or Jira ticket by gathering context, blockers, related work, code entry points, and unanswered questions.
---

# Prep Ticket

Gather ticket context when an ID is available; otherwise, use repository and diff evidence to produce a structured readiness summary in chat without inventing ticket requirements. In either mode, identify missing information, scan the codebase for related code, and give one suggested implementation approach.

> Plan-mode compatible. The Step 5 output is a chat reply, not a file. Do not call Write/Edit. If dispatched as a subagent, return the summary as your final message, not as a file write.

## Guiding principle — recommend the laziest thing that works

The best code is the code never written (YAGNI). This skill doesn't write code, so it bakes that bias into what it *recommends*. Carry it into the **Suggested Approach** and **Code-Review Readiness** sections (Step 5): recommend **exactly one** approach — the laziest that fully satisfies the ticket — then let `/grill-me` stress-test it.

**Laziest-first priority — take the first that fully satisfies the ticket:**
reuse an existing helper/module from the 3b scan → a native / stdlib / platform feature → an already-installed dependency (never add one for what a few lines do) → a few lines of new code → only then new structure.

**Recommend one approach, not a menu.** No "option A vs B", no fallbacks, no "flag the heavier design as opt-in", no scaffolding for a speculative future need — those alternatives are the bloat this skill exists to prevent; `/grill-me` is where heavier designs get surfaced if the simple one cracks. **Never lazy about:** validation at trust boundaries, error handling that prevents data loss, security, accessibility, or anything the ticket explicitly requires — lazy means less code, not a flimsier solution.

## Step 1: Resolve optional ticket context and platform

**Parse arguments:** The ticket ID is optional. The skill accepts an optional `<TICKET-ID>` and an optional `<platform>` (default: `linear` when ticket lookup is needed).

- `/prep-ticket ABC-123` → ticket = `ABC-123`, platform = `linear`
- `/prep-ticket ABC-123 jira` → ticket = `ABC-123`, platform = `jira`

If the user provided a ticket ID as an argument (e.g., `ABC-123`, `XYZ-456`), use it directly — uppercase if needed.

Otherwise, extract from the current git branch:

```bash
git rev-parse --abbrev-ref HEAD
```

Match the pattern `[a-zA-Z]{2,5}-\d+` (case-insensitive) and uppercase the result (e.g., `ABC-123`, `XYZ-456`).

If no ticket ID is found in either the argument or branch name, enter **repository-only mode**. Record `Ticket context: unavailable — no ticket ID was supplied or inferred from the branch`. Do not ask for an ID, invent a placeholder, or stop discovery.

## Step 2: Gather available context

In ticket-backed mode, run independent lookups in the same turn (parallel Bash calls). In repository-only mode, run the non-ticket provider availability probe below, skip ticket-specific queries, and continue with repository, branch, and diff evidence.

### 2a. Ticket details, relations, and comments

Only run the following ticket lookup when a ticket ID was resolved. A provider availability probe is separate from a ticket lookup and is safe to run without an ID.

**Repository-only provider availability probe:** use the selected platform (default `linear`) and run its version/help probe without any ticket ID or query:

```bash
linear --version
# or, when platform is jira:
jira --version
```

Capture and report the exact probe command, stdout, stderr, and exit status as separate fields. This probe runs without attempting a ticket lookup. Preserve a supplied or observed failure verbatim, including `linear: command not found`; do not turn a probe into a ticket lookup, pass a placeholder ID, or retry it in a loop.

**Linear** (default):

Extract the **team key** (prefix before the dash) and **ticket number** (digits after the dash) from the ticket ID. For example, `ABC-123` → team key `ABC`, number `123`; `XYZ-456` → team key `XYZ`, number `456`.

Replace `<NUMBER>` and `<TEAM>` in the query below:

```bash
linear api '{ issues(filter: { number: { eq: <NUMBER> }, team: { key: { eq: "<TEAM>" } } }) { nodes { identifier title description priority priorityLabel state { name type } labels { nodes { name } } estimate project { name description } parent { identifier title } relations { nodes { type relatedIssue { identifier title state { name type } } } } inverseRelations { nodes { type issue { identifier title state { name type } } } } comments(first: 30) { nodes { body createdAt user { name } } } } } }'
```

This single query fetches everything: details, relations, and comments.

**Jira**:

```bash
jira issue view <TICKET-ID> --plain --comments 10
```

Parse the output to extract: title, description, status, priority, labels, linked issues (blockers/relations), and comments. Linked issues and their types (blocks, is blocked by, relates to) are shown in the view output.

For richer parsing (if plain text is ambiguous):
```bash
jira issue view <TICKET-ID> --raw
```
This returns JSON — extract the same fields: title, description, priority, status, labels, linked issues with their states, and comments.

If the provider CLI or lookup fails, preserve the exact command, stdout/stderr, and exit status as the **exact lookup failure** in the report. Do not paraphrase an error into ticket facts, retry a failed lookup in a loop, or ask for a replacement ID. A failed ticket lookup falls back to repository-only mode when a repository is available.

In repository-only mode, record `Ticket context: unavailable`, `Ticket lookup: not attempted — no ticket ID`, and the provider probe's exact command/status/stderr separately. If the probe fails, copy its exact command/error (for example, `linear: command not found`) without normalizing it. Never fabricate ticket title, description, blockers, comments, requirements, or acceptance criteria.

### 2b. Existing branches and PRs

**Ticket-backed mode:**

```bash
git branch -a 2>/dev/null | grep -i "<ticket-id>"
gh pr list --search "<TICKET-ID>" --state all --json number,title,state,headRefName --limit 10 2>/dev/null
```

Replace `<ticket-id>` / `<TICKET-ID>` with the actual ticket ID (lowercase for branch grep, uppercase for PR search).

**Repository-only mode:** inspect committed branch changes, staged changes, and unstaged changes instead of filtering by a ticket ID. Detect the base/merge-base first, record the chosen base ref, then inspect all three change sets:

```bash
git rev-parse --abbrev-ref HEAD
git merge-base HEAD <base-ref>
git diff <base>...HEAD --stat
git diff <base>...HEAD --name-only
git status --short
git diff --cached --stat
git diff --cached --name-only
git diff --stat
git diff --name-only
git log --oneline -10
```

Use `git diff <base>...HEAD` for committed branch changes, `git diff --cached` for staged changes, and `git status --short` plus `git diff` for unstaged changes. Use all observed paths and changes as the scope for discovery. Do not invent ticket references or requirements from filenames, commit messages, or code patterns.

## Step 3: Codebase scan

### 3a. Project rules & coding standards

Read the standards this repo documents — the same places `/review` looks — but **scoped to this ticket's area**, not the whole repo:
- **Root `CLAUDE.md` / `AGENTS.md` / `README.md`**, plus any **architecture / standards anchor** they point to as the source of truth for review (e.g. `docs/architecture.md`, `CONTRIBUTING.md`, a `STANDARDS.md`). If a doc calls itself the "constitution" for PR review, treat it as the primary source.
- The **`CLAUDE.md` for this ticket's module/area**, discovered from the related files in 3b (e.g. `backend/src/<module>/CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`). Module guides usually carry the concrete typing / structure / testing rules.
- Relevant **ADRs** (`docs/adr/`) and the **type/lint configs** for the ticket's stack (pyright/mypy/ruff; tsconfig/biome/eslint) — only the ones touching the ticket's files.

Summarize the rules relevant to this ticket's area; you'll turn them into concrete, per-lens guidance in the **Code-Review Readiness** section of the report (Step 5).

### 3b. Related files

In ticket-backed mode, use the ticket description, labels, and any module/route/component names mentioned. In repository-only mode, use only the current branch, changed paths, recent diff, and repository documentation. Keep it lightweight: find 3-10 entry points the developer would start from, not an exhaustive list. Look for:
- Implementation files matching keywords from the ticket
- Test files adjacent to likely implementation files
- Similar past implementations that could serve as reference patterns

**Honor the repo's exemplar guidance:** if a CLAUDE.md flags a module as deprecated or "do not pattern-match" (e.g. a WIP prototype scheduled for rewrite), don't recommend it as a reference — point at the canonical module it names instead.

### 3c. Ticket references in code

Only when a ticket ID exists:

```bash
grep -r "<TICKET-ID>" --include="*.ts" --include="*.tsx" --include="*.py" --include="*.md" -l . 2>/dev/null | head -10
```

This catches TODOs, workarounds, or references already in the codebase. Without an ID, state that ticket-reference lookup is unavailable and rely on observed repository/diff evidence.

## Step 4: Readiness assessment

Keep ticket-backed facts separate from repository-only evidence. In repository-only mode, explicitly mark ticket context unavailable and do not infer ticket requirements, acceptance criteria, blockers, status, or comments from the codebase.

### 4a. Blockers

A ticket-backed report is **blocked** if `inverseRelations` contains any entry where `type` is `"blocks"` and the blocking issue's state type is NOT `"completed"` or `"canceled"`. A repository-only report must say `Blocking status: unavailable — no ticket context`; do not infer blockers from code or branch state.

For each blocker, note: ticket ID, title, current state, and whether it looks close to done (In Review, In QA) or far away (Backlog, Unstarted).

**Jira**: Check linked issues from the view output for link types like "is blocked by" or "Blocker". A ticket is blocked if any blocker's status is not "Done" or "Closed".

### 4b. Missing information

In ticket-backed mode, flag if any of these are true:
- Description is empty or very short (< 50 chars)
- No acceptance criteria visible in description or comments
- Priority is 0 (No priority)
- No estimate set
- Labels are missing
- No project context

In repository-only mode, list ticket context and ticket-specific requirements/acceptance criteria as unavailable. Do not invent acceptance criteria to fill the gap.

### 4c. Open questions

In ticket-backed mode, scan comments for unanswered questions — messages ending with `?` that have no follow-up response. Note any unresolved design decisions. In repository-only mode, report only questions evidenced by the repository/diff scan; do not create a ticket lookup question or a user question.

## Step 5: Reply to the user

Send the following directly as your chat message. Do not create a file. Do not call Write/Edit. The fenced block below is the *shape of the reply*, not a document to save. The report must contain one evidence-backed Suggested Approach; in repository-only mode, ground it only in observed repository/diff evidence and do not invent requirements or acceptance criteria.

```markdown
For ticket-backed mode:

# Prep Report: <TICKET-ID> — <title>

For repository-only mode (omit the ticket-backed heading and sections below that have no repository evidence):

# Prep Report: Repository-only — <branch>

## Ticket Context
- **Ticket ID**: <supplied but unavailable, or "Unavailable — no ticket ID was supplied or inferred from the branch">
- **Lookup**: <exact lookup failure, including command/output/status, or "not attempted — no ticket ID">
- **Requirements / acceptance criteria**: Unavailable — do not invent them

## Ticket Overview (ticket-backed mode only; otherwise mark every field unavailable or omit)
- **Status**: <state> | **Priority**: <priorityLabel> | **Estimate**: <estimate or "Unestimated">
- **Labels**: <labels>
- **Project**: <project or "None">
- **Parent**: <parent ticket or "None">

## Description
<ticket description, formatted for readability>

## Key Context from Comments
<summarize important comments — decisions, clarifications, extra requirements>
<or "No comments on this ticket.">

## Blocking Status
<"Unblocked — ready to start" or list each blocker with its state and proximity to completion>

## Related Work
- **Existing branches**: <list or "None found">
- **Related PRs**: <list with state or "None found">
- **Code references**: <files mentioning this ticket or "None found">

## Codebase Entry Points
<3-10 relevant files with brief explanation of each>

## Project Rules
<relevant rules from the repo's standards docs — root + module CLAUDE.md, the architecture/standards anchor, ADRs — or "No project rules files found">

## Missing Information
<list of gaps, or "All information present">

## Open Questions
<unresolved questions from comments, or "None identified">

## Code-Review Readiness
<What review will check — satisfy these up front. For each lens give 1-3 ticket-specific, actionable points sourced from the docs read in Step 3a (cite the doc); tailor to this ticket or mark "N/A for this ticket". Don't dump generic boilerplate.>
- **API-first** — <from the architecture/standards anchor; e.g. design typed entities + typed actions before the UI, a breaking versioned-API change is a review veto, no business rules in the frontend — they belong server-side. For a FE-only ticket: consume the typed contract, don't reimplement rules.>
- **Strong typing** — <from the module CLAUDE.md + type/lint configs; name the actual checkers/settings the repo uses (e.g. strict type-check + typed request/response schemas on the backend; strict TS + no `any` on the frontend).>
- **Modularity** — <from the module CLAUDE.md + ADR import boundaries; e.g. thin routers / logic in services, the repo's layering (component→hook→service), respect import boundaries, reuse the helpers found above, follow the canonical module exemplar — not a deprecated one.>
- **Functional programming** — pure functions, immutability, isolate side-effects/I/O at the edges, prefer composition. *(Not yet a documented standard in this repo — treat as a general guideline.)*
- **Simplicity / YAGNI** — the simplest workable solution that satisfies the ticket: no abstraction with one caller, no config for a constant, no new dependency for what a few lines do, no code for a speculative need. Shortest diff, fewest files, reuse the helpers from 3b before adding new ones. *(General YAGNI guideline — see the Guiding principle; not a repo-documented standard.)*

## Suggested Approach
<**Exactly one** approach — the laziest that fully satisfies the ticket, or the observed repository scope in repository-only mode — as 3-5 concrete bullets: a starting hypothesis for `/grill-me` to stress-test, not a final plan. In repository-only mode, use exactly one lazy evidence-backed suggested approach and ground every bullet in observed repository/diff evidence. Apply the laziest-first priority from the Guiding principle: reuse a helper/module from 3b → native/stdlib → an already-installed dependency → a few lines → only then new structure. Don't present alternatives, fallbacks, or "for later" options. Keep whatever the ticket requires when requirements are available; when they are not, do not invent requirements or acceptance criteria.>

### Getting Started
1. **Ticket-backed mode**: create a feature branch from `develop` when needed: `git checkout develop && git pull && git checkout -b feature/<ticket-id>-<short-desc>`
2. **Repository-only mode**: keep the current branch and report its exact name; do not create a ticket-named branch without an ID.

### Next step
Run `/grill-me` on the Suggested Approach above — it will interrogate the open questions and design decisions one at a time. (Use `/grill-with-docs` if you also want CONTEXT.md/ADRs updated as decisions land.)
```

## Edge cases

- **Ticket not found or platform CLI fails**: Preserve the exact lookup command, output, and exit status; mark ticket context unavailable and continue repository-only discovery when a repository exists. Do not retry in a question loop.
- **Jira CLI not installed**: If platform is jira but `jira` is not found, record the exact failure and continue repository-only discovery when possible.
- **Unknown platform**: If platform argument is not `linear` or `jira`, default to Linear with a note
- **Not in a git repo**: Without a ticket ID, report that repository evidence is unavailable and stop without inventing requirements. With a ticket ID, fetch ticket context from the platform only.
- **Ticket already Done/Canceled**: Note prominently — user may be prepping the wrong ticket
- **No CLAUDE.md or README.md**: Skip project rules section, note "No project rules files found"
- **Repo documents none of the standards** (no CLAUDE.md / architecture anchor): emit the five Code-Review Readiness lenses with their generic defaults + a one-line nudge to document standards; don't invent repo-specific rules
- **Non-code or trivial ticket** (dependency bump, docs, config): condense the Code-Review Readiness lenses or mark them "N/A for this ticket" — keep the report scannable, don't force all four
- **gh CLI unavailable**: Skip PR search, note in Related Work section
