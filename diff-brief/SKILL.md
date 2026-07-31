---
name: diff-brief
description: Use when an arbitrary PR, branch, commit, or range—especially someone else's change—needs a diff brief, change summary, risk map, or fast review triage.
---

review triage: not `explain-diff` teaching, `check-contract`
expected-versus-actual auditing, or `clean-up`/`review-swarm` finding or fixing.

Determine the base and head. For a merged PR: original PR base/head range as the
review target; shipped/squash commit separately when different; cite the snapshot
actually inspected. For other targets: one immutable base/head pair. Record
repository/base SHA/head SHA/target URL or ID/verification limits.

Read diff and surrounding code; reverse-summarize code as shipped, not
author/agent memory. Description/ticket are claims. Cite claims with a forge
permalink or `file:line`. Label only material findings/unknowns `Fact`,
`Inference`, or `Unknown`. Grounded summary sentences need citations, not labels.
No claim without evidence.

Cover every changed file with `SAFE | LOW | MEDIUM | HIGH`, evidence, and action.
Risk = consequence/blast radius; review priority is separate. `SAFE` means
non-executable docs or test-only changes that cannot alter build/release/runtime
artifacts. Changed tests may affect verification outcomes but remain SAFE
consequence risk. A weak test can be SAFE file risk yet high review priority.
`Config/scripts/CI`: never SAFE merely for being non-production.
`LOW`: localized/reversible, limited consumers, outside sensitive boundaries.
`MEDIUM`: shared runtime/operational behavior or cross-module/caller blast radius,
bounded/reversible; not `HIGH`.
`HIGH`: engaged auth/tenant/billing/migrations/data loss/concurrency/public
API/irreversible risk. Fuzzy responsibility is an
`UNCLEAR` finding and cannot be SAFE or LOW.

Inspect surrounding code: existing helpers/duplicate implementation; tests
against risky behavior; API shape, scope, over-defensiveness, performance,
maintainability, YAGNI. Clean dimensions: one compact line,
`Checks: NO ISSUE — ...` (`NO ISSUE` with evidence). Reuse `NO ISSUE`: compact
search provenance—scope, symbols/patterns, closest candidate inspected;
repository-level helper/reuse search evidence. Expand concern/unknown dimensions
only; omit irrelevant high-risk domains.

With subagents, dispatch one fresh-context read-only auditor with immutable
target/diff plus draft—not author memory. It challenges only shipped behavior,
reuse/closest existing candidate, risky tests, higher-level decision gaps; returns
evidence-only corrections/unknowns; main agent reconciles the final brief. This is
one verification pass, not review-swarm/personas/posting/fixing. Without
subagents, record `Fresh-context pass: unavailable` as `Unknown`.

Default: 600 words or fewer. Use one evidence-dense table and 3-7 focused-tour
and findings items total, covering load-bearing hunks in reading order. Do not dump the diff.
With >20 changed files, group low-risk files by shared
responsibility but account for every path.

## Verdict

## Behavior as shipped

## Review map

## Focused tour

## Findings and unknowns

## Verification signal

Executed checks → sibling `<report-stem>.verification.txt`: immutable snapshot,
exact command, exit status, concise raw/result summary. `Verification signal`
cites its local path. No preserved evidence → check claim is
`Unknown`/unverified, not proof.

## Recommended next action

End the persisted report with this compact footer:

## Handoff
local report path; exact optional Snapdoc publish command.

This is read-only and report-only. Do not modify code, post PR comments, or
publish externally without an explicit user request. Always save the Markdown
report locally in an ignored output location. Mermaid only when it materially
clarifies at least three interactions/state transitions. Publish with
`snapdoc publish <report>.md --markdown --title "<title>"`; return stable URL.
Video belongs to `qa-pr`.
