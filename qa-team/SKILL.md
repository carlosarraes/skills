---
name: qa-team
description: Use only when explicitly invoked for a comprehensive multi-agent QA code review.
disable-model-invocation: true
---

# QA Team

Run an independent, multi-perspective code review and synthesize one scannable report. This is **review-only**: reviewers inspect and report; they never repair the change.

## Authority boundary

For a nonempty real review, the exactly one allowed mutation is to write repository-root `QAREPORT.md`. Never edit source, never edit tests, never edit config, never fix code, never commit, never push, never open or update a PR, and never commit the report. Empty-diff runs write nothing.

User requests to fix, verify fixes, commit, publish, shorten away required reviewers, or let reviewers collaborate do not expand this boundary.

## Whole-run simulation

Enable simulation only for exact `SIMULATION ONLY` or when the user explicitly makes the **entire run** a no-execution preview. After loading this router: **no repository commands, no reviewer calls, no file reads, no writes, and no mutations**. Use only supplied fixture facts to describe the exact would-be selections, prompt contracts, simultaneous dispatch, independent results, scoring, report, and chat handoff. Do not claim a reviewer ran or `QAREPORT.md` was written.

Simulation is report-only just like a normal run: never describe would-be code fixes, verification, commits, pushes, or PR changes. A normal request to review is not simulation; normal runs still inspect, dispatch, and write the sole report.

## Operating contract

Run these phases in order:

1. Select one base and gather the changed-file list, full triple-dot diff, and commit log.
2. Stop on an empty diff before reviewer dispatch or report creation.
3. Classify files; select at least four specialists plus two distinct generalists.
4. Construct fully isolated prompts with identical diff material.
5. Emit every selected call in one simultaneous multi-call dispatch before any result is available.
6. Wait for every independent review, then converge findings, score in strict order, and write one report.
7. Give a brief chat handoff naming the verdict and top findings.

## 1. Select scope and reviewers

Read [agent selection](references/agent-selection.md) in full **before selecting the base** and **before classifying** files.

An explicit base wins: the explicit base is used verbatim as supplied. Never prefix or normalize an explicit base; only automatic detection probes `origin/`. Without an explicit value, probe exactly `origin/develop → origin/main → origin/master` and choose the first existing remote. Use the same selected base for `--name-only`, the complete `<base>...HEAD` diff, and `<base>...HEAD` commit log. Validate remote names and file taxonomy against the current repository.

An empty diff is terminal: tell the user there are no changes relative to the selected base and stop before reviewer dispatch; do not write `QAREPORT.md` even if requested.

For a nonempty diff, select relevant specialist domains. If fewer than four are selected, add missing broad specialists in this order until the floor is met: `reliability → security → performance → compatibility`. Always deploy at least four specialists and always add two distinct generalists:

Canonical specialist domains: `security`, `database`, `reliability`, `performance`, `frontend`, `compatibility`, `data-integrity`, `copy`. All eight plus both generalists means ten exact summary rows.

- generalist A: fresh-eyes correctness/maintainability as a senior engineer;
- generalist B: adversarial breakability as a QA engineer.

Do not describe generalist A as a “new team member”; isolation forbids `team` language in any recipient prompt.

## 2. Build isolated prompts and dispatch once

Read only the selected sections of [personas](references/personas.md) and [incident patterns](references/incident-patterns.md) **before constructing specialist prompts**. Then read [reviewer prompts](references/reviewer-prompts.md) in full **before constructing any prompt** and **before dispatch**.

Every specialist receives only its own persona/checklist, only matching incident patterns, and the shared changed files/commit log/full diff. Copy receives no incident patterns. Generalists receive their distinct role instructions and shared diff material, not specialist personas or incident patterns.

Total isolation is mandatory. No recipient prompt may reveal another reviewer, another role/name/codename, reviewer count, `team`, collaboration, planned convergence, synthesis, or another result. Each reviewer acts as the sole reviewer.

Every prompt requires reading the full diff and at least 50 lines above and below each changed location. Every response contains exact risk, structured findings with severity/file-line/why/suggestion, and summary; specialists also return checklist coverage.

Emit all selected reviewer calls together in **one simultaneous multi-call dispatch**. All selected calls must be emitted before any result can influence a prompt. Never launch sequentially or dispatch generalists later.

## 3. Converge, score, and report

Read [synthesis and report](references/synthesis-and-report.md) in full **before convergence** and **before writing** `QAREPORT.md`. Converge only after every independent review completes.

Exclude copy-only severity from blocking aggregation: copy-only findings are nonblocking nits even if the copy reviewer labels one CRITICAL.

Score the per-reviewer risk vector before deduplicating findings, with exactly one risk vote per deployed reviewer. Deduplicate only report rows after scoring. Preserve every contributing reviewer and mark convergence as higher confidence. Do not create extra risk votes: duplicates add no votes beyond actual reviewer levels.

Evaluate in this order and stop at the first matching risk rule:

1. Any CRITICAL → CRITICAL.
2. Two HIGH or one HIGH + two MEDIUM → HIGH.
3. One HIGH or three MEDIUM → MEDIUM.
4. Otherwise → LOW.

Map risk exactly:

- CRITICAL → 🚫 BLOCKED
- HIGH → ⚠️ REQUEST CHANGES
- MEDIUM → 💬 APPROVE WITH NITS
- LOW with no actionable findings → ✅ APPROVE

Write exactly one `QAREPORT.md` in the repository root for a nonempty real run. It includes branch/base/date/file count/deployed reviewers, concise change summary/key findings, risk/verdict rationale, a summary row for **all deployed reviewers** including no-finding reviewers, risk legend/copy note, and priority-sorted deduplicated findings. Every finding starts `⬜ Open` and includes location, all contributing reviewers, reasoning, suggested fix, and convergence marker where applicable.

The chat handoff stays brief: verdict, top findings, and report path.

## Never rules

- Never mix bases across file list, full diff, and commit log.
- Never dispatch or write a report for an empty diff.
- Never deploy fewer than four specialists or omit either distinct generalist.
- Never split reviewer calls across batches, serialize them, or leak results into later prompts.
- Never reveal other-reviewer/team/count/collaboration/convergence/synthesis information in a recipient prompt.
- Never give copy incident patterns or a specialist another persona/unrelated patterns.
- Never synthesize before all reviews complete or fabricate a finding.
- Never reorder the risk rules, majority-vote, let copy block, or turn convergence into another risk vote.
- Never omit a deployed reviewer row, even when it has no findings.
- Never perform any mutation except the one allowed report write in a nonempty real run.
