---
name: oss-scout-issues
description: Use when choosing a contribution issue inside a known open-source repository, ranking candidates by feasibility, competition, and career value.
---

# oss-scout-issues

Given one repo, ranks its open issues by how clearly actionable they are, how hard the work is, and whether someone already has a PR out for it — plus how much the project's name carries on a CV.

## Core principle

**Clarity beats difficulty.** The main reason a contribution stalls is not that the work was hard, it's that the issue never said what "done" looks like. Ranking is therefore clarity-first, with difficulty as a filter you apply yourself.

## When to use

- "which issue should I pick in <repo>?"
- "is contributing to posthog/deno/scylla worth it for my career?"
- "give me the easy ones" / "something meatier"
- Before starting work: "has someone already claimed this?"

Use `oss-scout` instead to *find* repos. This skill assumes you already picked one.

## Relationship to oss-scout

They optimise for opposite things on one axis, deliberately:

| | oss-scout | oss-scout-issues |
|---|---|---|
| Corporate-backed repos | **rejects** (crowded, `needs_help: false`) | **welcomes** (that's where CV signal lives) |
| Question answered | "who needs help?" | "what should I do here, and does it count?" |

So do not pipe one into the other blindly — a repo oss-scout rejected may be exactly what you want here.

## Usage

```bash
scripts/scan.py posthog/posthog          # fetch + judge + verify -> data/<repo>.json
scripts/show.py posthog/posthog --difficulty easy medium --hide-taken
```

`scan.py` costs API calls; `show.py` is free and re-filterable. Run `--help` for flags.

## How competition is detected

Three signals, cheapest first:

1. **Assignee / comment count** — from the bulk listing, zero extra cost
2. **Open linked PRs** — one GraphQL call covering all finalists at once (`CROSS_REFERENCED_EVENT`)
3. **Claim language in recent comments** — "I'll take this", "working on this", "assign me"

Only the top finalists get 2 and 3, because they cost real quota. Anything unverified is labelled `_competition not checked_` rather than silently presented as free.

## Non-obvious constraints

- **Blocking labels must be filtered mechanically, not judged.** An issue labelled `waiting-on-upstream` or `needs-design` reads as clear and easy to a model — the text is fine, the work just cannot start. On sudo-rs this removed 12 of 79 items. `drop_reason()` owns this; the model never sees them.
- **`/issues` returns pull requests too.** Every item with a `pull_request` key must be dropped or your "issues" list is half PRs.
- **Every drop is tallied and printed.** A filter that silently removes two thirds of a repo's issues reads as "this repo has nothing", which is a different and wrong conclusion.
- **Bulk listing is cheap, per-issue is not.** 100 issues per call *including* body and labels; anything per-issue multiplies fast on a big repo.
- **GraphQL has a separate quota** from REST core, so verification does not compete with REST-heavy scanning.
- **CV signal is a repo property, not an issue property** — judged once per scan, not per issue.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Ranking by difficulty first | Surfaces "easy" issues that are one-line wishes with no spec |
| Letting the model decide if an issue is blocked | It reads the prose, not the label, and calls a blocked issue easy |
| Trusting "no assignee" as unclaimed | Many projects never assign; the PR is the real signal |
| Judging CV signal per issue | Pays N times for one answer about the org |
| Scanning a huge repo with no comment cap | Ranks issues with 40-comment debates already underway |
