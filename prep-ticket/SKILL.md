---
name: prep-ticket
description: "Prepares a developer to work on a Linear ticket by fetching all context, checking blockers, scanning the codebase, and producing a structured readiness report with implementation guidelines. Use this skill whenever the user says 'prep ticket', 'prep-ticket', 'prepare ticket', 'get ready for ABC-123', 'prep XYZ-456', 'analyze ticket', 'ticket prep', 'break down this ticket', 'ticket readiness', 'is DBZ-789 ready', 'what's blocking DEV-42', 'what do I need to know about QA-1024', or wants to understand a Linear ticket before starting work on it. Also trigger when the user mentions checking if a ticket is unblocked, gathering ticket context, or preparing to implement a specific ticket. Supports Linear (default) and Jira — pass platform as second argument (e.g., '/prep-ticket ABC-123 jira')."
---

# Prep Ticket

Gather all context for a Linear ticket, check if it's unblocked, identify missing information, scan the codebase for related code, and produce a readiness report with a suggested implementation approach.

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

### 3a. Project rules

Read CLAUDE.md and README.md at the repo root (if they exist). Summarize rules relevant to this ticket's area.

### 3b. Related files

Based on the ticket description, labels, and any module/route/component names mentioned — search for likely related files. Keep it lightweight: find 3-10 entry points the developer would start from, not an exhaustive list. Look for:
- Implementation files matching keywords from the ticket
- Test files adjacent to likely implementation files
- Similar past implementations that could serve as reference patterns

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

## Step 5: Output report

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
<relevant rules from CLAUDE.md / README.md, or "No project rules files found">

## Missing Information
<list of gaps, or "All information present">

## Open Questions
<unresolved questions from comments, or "None identified">

## Suggested Approach
<2-5 bullet points on how to implement, based on ticket content and codebase patterns>

### Getting Started
1. **Create a feature branch** from `develop`: `git checkout develop && git pull && git checkout -b feature/<ticket-id>-<short-desc>`
2. Follow the approach above

### Implementation Guidelines
- **Leverage existing code** — find similar implementations and follow established patterns
- **KISS** — keep it simple, avoid over-engineering
- **Follow project rules** — CLAUDE.md and README.md conventions apply
- **TDD** — where applicable, write tests first: <list 2-4 specific testable areas, or note "this ticket type (e.g., dependency upgrade) benefits more from smoke testing than unit tests">
- **Ask before assuming** — flag anything unclear before starting implementation
```

## Edge cases

- **Ticket not found**: Report the error, ask user to verify the ticket ID
- **Platform CLI fails**: Note which platform CLI is unavailable; proceed with codebase scan only if a branch exists
- **Jira CLI not installed**: If platform is jira but `jira` not found, report error and suggest: `brew install ankitpokhrel/jira-cli/jira-cli`
- **Unknown platform**: If platform argument is not `linear` or `jira`, default to Linear with a note
- **Not in a git repo**: Skip branch extraction and codebase scan; fetch ticket from the platform only
- **Ticket already Done/Canceled**: Note prominently — user may be prepping the wrong ticket
- **No CLAUDE.md or README.md**: Skip project rules section, note "No project rules files found"
- **gh CLI unavailable**: Skip PR search, note in Related Work section
