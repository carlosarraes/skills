# Reviewer Prompt Contracts

Read this file before building any reviewer prompt or dispatching reviewers.

## Shared evidence and context duty

Every recipient gets byte-equivalent changed-file list, commit log, and full diff from the selected base. Require the reviewer to read the full diff and at least 50 lines above and below every changed location before applying its checklist.

Every reviewer is read-only: inspect and report only; no fixes, source/test/config edits, report writes, commits, pushes, or PR actions.

## Isolation scan

Each recipient believes it is the sole reviewer. Its prompt may name its own focus but must contain:

- no other reviewer identity, codename, role, or result;
- no reviewer count or dispatch topology;
- no `team`, collaboration, coordination, validation-by-peer, or shared-review language;
- no convergence, synthesis, future aggregation, or report plan.

Run this leak scan on every final prompt before dispatch.

## Specialist recipe

A specialist prompt contains, in order:

1. its focus role;
2. only its own persona description and checklist from `personas.md`;
3. only relevant incident patterns from `incident-patterns.md`;
4. shared changed files, commit log, and full diff;
5. context duty, read-only rule, and exact response schema.

Copy receives no incident patterns and no `Known failure patterns` section. No specialist receives another persona or unrelated patterns.

Exact specialist response:

```text
**Risk Level:** CRITICAL / HIGH / MEDIUM / LOW / NONE
**Findings:**
- **[SEVERITY]** `file:line` — description
  - Why it matters: explanation
  - Suggestion: specific fix or mitigation
If none: "No issues found in my focus area."
**Checklist Coverage:** each item as [x] reviewed or [-] not applicable
**Summary:** one brief paragraph
```

## Distinct generalist recipes

Generalist A is a **fresh eyes** senior engineer focused on correctness, safety, error handling, concurrency, edge cases, readability, and maintainability. Never call it a “new team member” or include `team` language. It ignores style/formatting/minor nits.

Generalist B is an **adversarial** QA engineer focused on malformed/huge/empty/malicious input, dependency failure, concurrency, scale, mixed-version deployment, misuse, and breakability. It ignores style/readability.

Generalists receive no specialist persona or incident-pattern material. Both use the shared evidence/context/read-only rules and this exact response:

```text
**Risk Level:** CRITICAL / HIGH / MEDIUM / LOW / NONE
**Findings:**
- **[SEVERITY]** `file:line` — description
  - Why it matters: explanation
  - Suggestion: specific fix or mitigation
If none: "No issues found."
**Summary:** one brief paragraph
```

## Dispatch topology

Build and isolation-scan every prompt first. Then emit **all selected calls** in one simultaneous multi-call dispatch, before any result is available. Never await one call before emitting another, never use multiple dispatch waves, and never reveal completion order.
