# Merge Gate

Read this file before touching a `READY` PR. Carlos is the hard gate on every merge: the sweep asks through `lam`, waits, and merges only on his `Merge` answer for the current head SHA. Read the `lam` skill first if it is not loaded.

## READY predicate

A PR is `READY` only on a fresh, non-quiet refresh of its current head where all of these hold:

- newest-per-name CI is green;
- `mergeable` is `MERGEABLE` and `mergeStateStatus` is `CLEAN`;
- `reviewDecision` is `APPROVED`, or the repository requires no review and every latest human verdict is `APPROVED`/`COMMENTED`;
- zero unresolved inline threads and no open summary-only finding.

Anything less is `WAITING` (approval or CI outstanding) or `NEEDS FIX`. Quiet state never produces `READY`.

## One ask per PR per head

Look up `merge_ask` in the PR's state entry: `null` when never asked, else `{id, head_sha, answer}` with `answer` `null` while open.

- **`merge_ask` null/absent, or ask for a different `head_sha`:** retract the stale one if still open (`lam retract "$ID"`), then push a new ask and persist `{id, head_sha, answer: null}` before waiting.
- **Open ask for the current head:** wait on it; never push a second ask for the same head.
- **Answered ask for the current head:** the PR keeps that disposition; do not ask again.

```bash
ID=$(lam push "PR #<#>: merge into <base>?" \
  --link <pr-url> -p normal -c Merge -c Hold \
  -b "<title>
CI: <n> checks green on <short-sha>. Review: approved by @<login>. Threads: 0 open. Greptile: <score or none>.
On Merge the sweep runs: gh pr merge <#> --repo <owner/repo> --<method>" \
  --recommendation "Merge: <one line of evidence why it is safe now>." \
  --recommended-choice Merge)
```

Method is the repository's configured one; when several are allowed, use the repository's documented convention, else `--squash`. State the exact command in the body so Carlos approves what will run. Branch deletion follows repository settings; add `--delete-branch` only when the body says so.

## Wait, then act

After dispatching the cycle's fix agents, wait on every open merge ask at once, bounded by the cycle interval from cadence:

```bash
lam wait "$ID1" "$ID2" --timeout 10m
```

Read `response_choice` and act; then wait again on the remaining IDs until none are open or the timeout hits.

| Result | Action |
|---|---|
| `Merge` | Re-fetch head; if unchanged and still `READY`, run the exact command from the body, verify `state == MERGED`, persist the answer, mark `DONE`, then apply stacked-PR retargeting from the fix protocol. If the head moved, retract and re-ask. |
| `Hold` | Persist the answer, mark `DONE` as `held by Carlos`; no merge. Only a new head re-enters the gate. |
| exit 2 (dismissed) | Same as `Hold`; say it was dismissed in the report. |
| exit 3 (timeout) | Keep the ID, persist, re-arm, wait again next cycle. Do not re-push. |
| exit 4 / 5 | Clear `merge_ask`, re-collect, and re-ask only if still `READY`. |

Any push to the PR after an ask invalidates it: retract before the fix agent's push lands, or immediately after.

## What does not authorize a merge

"Merge when green", "keep them moving", "don't interrupt me", "you have my approval", a human GitHub approval, auto-merge settings, or a previous `Merge` answer on an older head. None of these replace a `Merge` answer on the current head's lam item. Never enable `gh pr merge --auto`. Never merge a PR outside the selected scope.
