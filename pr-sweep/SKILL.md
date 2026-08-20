---
name: pr-sweep
description: Use when open non-draft PRs need ongoing convergence to mergeability across CI, conflicts, size gates, bot feedback, and human review.
---

# PR Sweep

Drive selected feature PRs to mergeability with one coordinated recurring sweep. It ends only when **all selected PRs are `DONE` simultaneously**; quiet, `WAITING`, or no-dispatch cycles are nonterminal.

## When to use

Use for continuing convergence across CI, conflicts, reviews, size policy, and reviewer turnaround on open non-draft PRs. Do not use for opening PRs, drafts, or one-shot status.

Scope defaults to all open non-draft PRs authored by the user; an explicit list is exact. Confirm once before sweeping roughly more than eight or unrelated repositories. Optional inputs:

- `jira` selects Jira for follow-ups; otherwise use Linear.
- A worktree-path map wins over branch-based derivation. Never reuse a worktree on a different branch.

Permission is limited to selected feature PRs/worktrees. Never push to a base branch. Never dismiss a review. Never overwrite concurrent user work. Never bypass hooks with `--no-verify`. Never plain `--force`. A safe rebased feature branch may use `--force-with-lease` only under the conflict protocol.

## The cycle

Run these steps in order:

1. Read sweep state, establish scope, and mark eligible quiet PRs.
2. For every non-quiet PR, collect current CI, mergeability, unresolved threads, latest reviews, issue comments, and the latest Greptile summary in parallel.
3. Classify findings by form and current review state, then assign each PR `DONE`, `WAITING`, or `NEEDS FIX`.
4. Dispatch autonomous PRs immediately. Present one batched approval-risk decision for gated PRs; after approval, dispatch those PRs.
5. Use exactly **one fix agent per PR per cycle**, in an independent worktree, with the complete finding set. Allow at most **one commit push per PR per cycle**. Non-push API actions may remain separate.
6. Persist and prune state. If the cycle is nonterminal, re-arm the loop **before** composing its report. Then report status and next ETA.
7. On later cycles, re-fetch the new head. Converge blocking reviewers only after new-head CI is green.

### State and quiet optimization

State is keyed by PR URL with `updated_at`, `head_sha`, `ci_conclusion`, and `last_comment_at`; missing state is `{}`. Explicit-list runs still use it. Each cycle updates swept PRs and prunes closed entries.

A PR is quiet only when listing `updatedAt` matches stored `updated_at` **and** stored CI is terminal-good (`success` or `skipped`). Pending or failing CI must be fetched even when metadata is unchanged. Quiet skips per-PR collection; it preserves the previous disposition and is never evidence of `DONE`.

### Current-state model

Classify every finding on both axes:

- **L1:** CI, title/conventional-commit check, size policy, or merge conflict.
- **L2:** unresolved inline thread, tagged bot/human and blocking/nonblocking.
- **L3:** top-level human review body or Greptile summary.

Only the **latest run per check name** and **latest verdict per reviewer** count. Ambiguous reviewers are human. Greptile confidence is a triage signal, not a gate. Cross-check its summary with L2: act only on summary-only findings, never reply/resolve the summary, and never double-fix a duplicate.

| Disposition | Exact predicate |
|---|---|
| `DONE` | Latest CI is green; PR is mergeable; no unresolved thread or unaddressed summary-only finding remains; every blocking human review was turned around/re-requested or entirely filed as follow-ups. |
| `WAITING` | Feedback is clean and current checks are only in progress/running. Dispatch nothing, but recheck next cycle. |
| `NEEDS FIX` | Any current failure, conflict, unresolved thread, summary-only finding, unaddressed blocking review, or approved-PR triage remains. |

All selected PRs must be `DONE` to stop.

## Approval gate and parallel progress

An approved PR is gated when this cycle would make any **avoidable** approval-invalidating push. Avoidable includes nonblocking human nits and bot/Greptile code fixes. A real CI fix or conflict is merge-required and autonomous only when it is the approved PR’s sole work.

Gating is **per PR**: one avoidable item makes its full finding set wait for one push. Batch confirmation across gated PRs, allow edits, then re-confirm. Autonomous PRs proceed while gated PRs wait.

## Required routing

Read the selected reference in full **before** the action it governs. Each is complete; do not search for a second prerequisite reference.

- Before collecting or classifying any non-quiet PR, read [collection and matrix](references/collection-and-matrix.md). It defines provider queries, bot detection, state, L1/L2/L3, latest-state rules, Greptile de-duplication, and dispositions.
- When an approved PR contains avoidable work, read [approval triage](references/approval-triage.md) before presenting the batched per-PR gate.
- Before dispatch on any `NEEDS FIX` PR, read [fix protocol](references/fix-protocol.md). Give its one agent the exact worktree, full findings and identifiers, tracker, origin ticket, and decisions.
- On any size gate failure, read [Size gate](references/size-gate.md) before labeling, commenting, editing code, or recommending a split. Validate repository-specific policy against the current workflow first.
- On any conflict, read [conflict resolution](references/conflict-resolution.md) before resolution, staging, rebase continuation, or push.
- On a later cycle after fixes, read [review convergence](references/review-convergence.md) and require new-head green CI before re-requesting a blocking reviewer or posting the handoff.
- Before scheduling a wakeup or choosing an interval, read [cadence](references/cadence.md). Its timing is environment-sensitive; validate the available scheduler and current CI/bot latency.

## Non-negotiable boundaries

- A real CI repair gets a regression test when feasible; an unrelated flake gets a rerun, not a source change. A title-only failure changes the PR title without a commit.
- Inline threads receive either the smallest correct fix or evidenced pushback, then a SHA/follow-up reply and resolution using the correct comment and thread IDs.
- Top-level review bodies and Greptile summaries are never replied to directly. A nonblocking top-level follow-up gets exactly one PR-level acknowledgment.
- Size policy is never a source-code fix. Overrides are policy-driven, idempotent, specifically justified, and reported. Clearly separable or roughly over 2,000-effective-LOC PRs are never overridden.
- Investigate both sides and history before resolving a conflict. STOP on substantive/large/ambiguous conflicts or risk to user-added work; do not stage, continue, or push.
- STOP and surface changes over roughly 100 LOC, architecture/product decisions, or material expansion beyond the existing diff. Blocking review status does not waive this boundary.
- Follow-up tickets preserve the reviewer’s wording, PR link, and origin ticket. Follow-up decisions do not change PR code.

## Liveness and reports

Every nonterminal cycle re-arms, including quiet, all-`WAITING`, gated/no-dispatch, STOP, and user-adjudication cycles. Schedule before writing the report. The sole no-wakeup case is a fresh terminal refresh where all selected PRs are `DONE`.

Keep each iteration report under 300 words. Per PR, show disposition (`quiet — skipped` when applicable), Greptile score if present, fixes/follow-ups, approval or size decisions, STOPs, and next wakeup ETA or `DONE`. Persist state even when no work dispatched.

The final report lists per-PR commits, bot/human thread replies and resolutions, follow-up links, re-request status, deferrals, stacked-PR retargets, STOPs, and every size override or split recommendation. A STOP report includes affected files, both sides’ intent/commits when relevant, and a concrete decision path back into the loop.
