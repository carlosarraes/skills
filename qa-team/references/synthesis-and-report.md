# Synthesis and `QAREPORT.md`

Read this file only after dispatch, but before convergence, scoring, or writing the report.

## Convergence

Synthesize only after all reviews complete. Do not invent or strengthen findings beyond reviewer evidence.

Group findings only when they describe the same material concern and location. Produce one row, retain all contributing reviewers, and mark it convergent/higher confidence. A duplicate is **not another risk vote**; risk counts reviewer-returned levels once each. Materially different concerns remain separate.

Copy-only findings are always nonblocking LOW nits for aggregation, regardless of the copy reviewer’s label. A matching non-copy finding is scored from non-copy evidence normally. Matching generalist/specialist evidence raises confidence, not numeric vote count.

## Ordered risk and verdict

Evaluate top to bottom; the first match wins:

| Order | Reviewer levels after copy normalization | Overall | Verdict |
|---:|---|---|---|
| 1 | any CRITICAL | CRITICAL | 🚫 BLOCKED |
| 2 | two HIGH, or one HIGH + two MEDIUM | HIGH | ⚠️ REQUEST CHANGES |
| 3 | one HIGH, or three MEDIUM | MEDIUM | 💬 APPROVE WITH NITS |
| 4 | otherwise LOW/NONE with no actionable findings | LOW | ✅ APPROVE |

The compound HIGH rule precedes the one-HIGH MEDIUM rule. Do not majority-vote or alter thresholds under approval pressure.

## Write exactly one report

For a nonempty real review, write exactly one `QAREPORT.md` in the repository root. Do not commit it. This is the only allowed mutation.

Use compact emoji headings, tables, checklists, and short bullets. Include:

- metadata: branch, selected base, changed-file count, date, and complete deployed-reviewer list;
- 2–4 change-summary bullets and concise key findings;
- risk/verdict plus the exact rule that fired;
- one summary row for **all deployed reviewers**, including LOW/NONE/no-finding results;
- note that copy-only findings are nonblocking and matching generalists raise confidence;
- risk legend: 🔴 CRITICAL, 🟠 HIGH, 🟡 MEDIUM, 🟢 LOW, ⚪ NONE;
- deduplicated findings sorted CRITICAL → HIGH → MEDIUM → LOW.

Every finding row contains `⬜ Open`, priority, short title, `file:line`, all contributing reviewers, why it matters, suggested fix, and a convergence marker when 2+ reviewers independently matched. Preserve copy nits as LOW/nonblocking. Do not emit empty rows for reviewers without findings—their presence belongs in summaries.

Required findings columns:

```text
# | Status | Priority | Finding | Location | Contributing reviewers | Reasoning | Suggested fix | Convergence
```

The brief chat handoff names the verdict and top findings, then points to repository-root `QAREPORT.md`. It does not fix findings, commit the report, or narrate every reviewer.

In whole-run simulation, render the exact would-be report obligations/content from supplied results but perform no write. State explicitly that no review, report write, fix, verification, commit, push, or PR action occurred.
