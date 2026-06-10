---
name: prep-ticket
description: "Prepares a developer to work on a Linear ticket by fetching all context, checking blockers, scanning the codebase, and producing a structured readiness report, ending with a pointer to /grill-me to stress-test the suggested approach. Use this skill whenever the user says 'prep ticket', 'prep-ticket', 'prepare ticket', 'get ready for ABC-123', 'prep XYZ-456', 'analyze ticket', 'ticket prep', 'break down this ticket', 'ticket readiness', 'is DBZ-789 ready', 'what's blocking DEV-42', 'what do I need to know about QA-1024', or wants to understand a Linear ticket before starting work on it. Also trigger when the user mentions checking if a ticket is unblocked, gathering ticket context, or preparing to implement a specific ticket. Supports Linear (default) and Jira — pass platform as second argument (e.g., '/prep-ticket ABC-123 jira')."
---

# Prep Ticket

Gather all context for a Linear ticket, check if it's unblocked, identify missing information, scan the codebase for related code, and produce a structured readiness summary in chat with a suggested implementation approach.

> Plan-mode compatible. The Step 5 output is a chat reply, not a file. Do not call Write/Edit. If dispatched as a subagent, return the summary as your final message, not as a file write.

## Step 1: Extract ticket ID and platform

**Parse arguments:** The skill accepts `<TICKET-ID>` (required) and an optional `<platform>` (default: `linear`).

- `/prep-ticket ABC-123` → ticket = `ABC-123`, platform = `linear`
- `/prep-ticket ABC-123 jira` → ticket = `ABC-123`, platform = `jira`

If the user provided a ticket ID as an argument (e.g., `ABC-123`, `XYZ-456`), use it directly — uppercase if needed.

Otherwise, extract from the current git branch:

```bash
git rev-parse --abbrev-ref HEAD
```

Match the pattern `[a-zA-Z]{2,5}-\d+` (case-insensitive) and uppercase the result (e.g., `ABC-123`, `XYZ-456`).

If no ticket ID found in either the argument or branch name, ask the user: "Could not determine the ticket ID. What's the ticket ID (e.g., ABC-123, XYZ-456)?"

## Step 2: Gather context

Run both in the **same turn** (parallel Bash calls) — they are independent.

### 2a. Ticket details, relations, and comments

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

### 2b. Existing branches and PRs

```bash
git branch -a 2>/dev/null | grep -i "<ticket-id>"
gh pr list --search "<TICKET-ID>" --state all --json number,title,state,headRefName --limit 10 2>/dev/null
```

Replace `<ticket-id>` / `<TICKET-ID>` with the actual ticket ID (lowercase for branch grep, uppercase for PR search).

## Step 3: Codebase scan

### 3a. Project rules & coding standards

Read the standards this repo documents — the same places `/review` looks — but **scoped to this ticket's area**, not the whole repo:
- **Root `CLAUDE.md` / `AGENTS.md` / `README.md`**, plus any **architecture / standards anchor** they point to as the source of truth for review (e.g. `docs/architecture.md`, `CONTRIBUTING.md`, a `STANDARDS.md`). If a doc calls itself the "constitution" for PR review, treat it as the primary source.
- The **`CLAUDE.md` for this ticket's module/area**, discovered from the related files in 3b (e.g. `backend/src/<module>/CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`). Module guides usually carry the concrete typing / structure / testing rules.
- Relevant **ADRs** (`docs/adr/`) and the **type/lint configs** for the ticket's stack (pyright/mypy/ruff; tsconfig/biome/eslint) — only the ones touching the ticket's files.

Summarize the rules relevant to this ticket's area; you'll turn them into concrete, per-lens guidance in the **Code-Review Readiness** section of the report (Step 5).

### 3b. Related files

Based on the ticket description, labels, and any module/route/component names mentioned — search for likely related files. Keep it lightweight: find 3-10 entry points the developer would start from, not an exhaustive list. Look for:
- Implementation files matching keywords from the ticket
- Test files adjacent to likely implementation files
- Similar past implementations that could serve as reference patterns

**Honor the repo's exemplar guidance:** if a CLAUDE.md flags a module as deprecated or "do not pattern-match" (e.g. a WIP prototype scheduled for rewrite), don't recommend it as a reference — point at the canonical module it names instead.

### 3c. Ticket references in code

```bash
grep -r "<TICKET-ID>" --include="*.ts" --include="*.tsx" --include="*.py" --include="*.md" -l . 2>/dev/null | head -10
```

This catches TODOs, workarounds, or references already in the codebase.

## Step 4: Readiness assessment

### 4a. Blockers

A ticket is **blocked** if `inverseRelations` contains any entry where `type` is `"blocks"` and the blocking issue's state type is NOT `"completed"` or `"canceled"`.

For each blocker, note: ticket ID, title, current state, and whether it looks close to done (In Review, In QA) or far away (Backlog, Unstarted).

**Jira**: Check linked issues from the view output for link types like "is blocked by" or "Blocker". A ticket is blocked if any blocker's status is not "Done" or "Closed".

### 4b. Missing information

Flag if any of these are true:
- Description is empty or very short (< 50 chars)
- No acceptance criteria visible in description or comments
- Priority is 0 (No priority)
- No estimate set
- Labels are missing
- No project context

### 4c. Open questions

Scan comments for unanswered questions — messages ending with `?` that have no follow-up response. Note any unresolved design decisions.

## Step 5: Reply to the user

Send the following directly as your chat message. Do not create a file. Do not call Write/Edit. The fenced block below is the *shape of the reply*, not a document to save.

```markdown
# Prep Report: <TICKET-ID> — <title>

## Ticket Overview
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

## Suggested Approach
<2-3 seed bullets — a starting hypothesis to be stress-tested, not a final plan>

### Getting Started
1. **Create a feature branch** from `develop`: `git checkout develop && git pull && git checkout -b feature/<ticket-id>-<short-desc>`

### Next step
Run `/grill-me` on the Suggested Approach above — it will interrogate the open questions and design decisions one at a time. (Use `/grill-with-docs` if you also want CONTEXT.md/ADRs updated as decisions land.)
```

## Edge cases

- **Ticket not found**: Report the error, ask user to verify the ticket ID
- **Platform CLI fails**: Note which platform CLI is unavailable; proceed with codebase scan only if a branch exists
- **Jira CLI not installed**: If platform is jira but `jira` not found, report error and suggest: `brew install ankitpokhrel/jira-cli/jira-cli`
- **Unknown platform**: If platform argument is not `linear` or `jira`, default to Linear with a note
- **Not in a git repo**: Skip branch extraction and codebase scan; fetch ticket from the platform only
- **Ticket already Done/Canceled**: Note prominently — user may be prepping the wrong ticket
- **No CLAUDE.md or README.md**: Skip project rules section, note "No project rules files found"
- **Repo documents none of the standards** (no CLAUDE.md / architecture anchor): emit the four Code-Review Readiness lenses with their generic defaults + a one-line nudge to document standards; don't invent repo-specific rules
- **Non-code or trivial ticket** (dependency bump, docs, config): condense the Code-Review Readiness lenses or mark them "N/A for this ticket" — keep the report scannable, don't force all four
- **gh CLI unavailable**: Skip PR search, note in Related Work section
