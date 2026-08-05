# Approval-Risk Triage

Read this file when a currently approved PR has work that may create an avoidable commit. Approval is current only when the latest verdict per reviewer is `APPROVED`.

## Gate predicate

An approved PR is gated when **any avoidable push** is proposed:

- nonblocking human L2/L3 fix-here work;
- bot inline code fixes;
- Greptile summary-only code fixes;
- other deferrable changes not strictly needed for mergeability.

A real CI repair or safely resolvable conflict is merge-required and autonomous only when it is the PR's sole work. If the same PR also has one avoidable item, gating is **per PR**: its full L1/L2/L3 set waits and later batches into one push. Non-push actions ride with that agent rather than splitting ownership.

Do not hold autonomous PRs behind the gate. Start their independent agents while collecting one batched user decision for gated PRs.

## Triage rubric

- **fix-here:** typo, dead import, narrow rename, missing documentation, already-touched null guard, test-name fix, or similarly cheap in-scope correction.
- **borderline — lean fix-here:** roughly 1–20 LOC in an already-touched file with no new feature surface or test harness.
- **follow-up:** new feature, multi-file/architectural refactor, scope beyond acceptance criteria, or reviewer language such as “non-blocking” / “in a follow-up.”
- **do not file:** the reviewer explicitly says it is only a thought and not to file it. Preserve that instruction; acknowledge and resolve an inline thread without code/ticket.

Reviewer-explicit follow-up and do-not-file instructions override the generic rubric.

## One batched confirmation

Present one batch across every gated PR. For each item show PR, approver, form, short quote, recommendation, reason, and whether it adds code or a follow-up. State that any fix-here commit invalidates the named approval. Example shape:

```text
APPROVED-PR triage

PR #820 (approved by @alice)
  [fix-here] inline: rename cfg → config — one-line in-scope rename
  [follow-up] overall: extract auth layer — architectural scope expansion

Recommendation: 1 fix-here, 1 follow-up.
Pushing fix-here invalidates @alice's approval. Proceed? (yes / no / edit)
```

If the user edits classifications, show the updated batch and **re-confirm**. Confirmation is per PR: no mutation or push for that PR before approval. User urgency or a bot's certainty does not waive the gate.

## Edge cases

- Older approval followed by the same reviewer's `CHANGES_REQUESTED`: no approval gate; use the latest blocking verdict.
- One approver plus another blocking reviewer: handle the blocking set autonomously only if no avoidable approved-PR work exists; otherwise gate the entire PR. Later re-request the blocker, not the approver.
- Approved PR with only real red CI: repair autonomously and report that the approval was invalidated by merge-required work.
- Approved PR with real red CI plus one bot code fix: wait on the entire PR, then give one agent both findings and one commit push.
- Declined fix-here: preserve it as an explicit deferral in the report. A follow-up gets provenance; a bare decline does not silently erase the finding.

Always surface approval invalidation in the cycle and final reports.
