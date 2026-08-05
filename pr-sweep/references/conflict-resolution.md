# Conflict Investigation and Safety

Read this file before resolving, staging, continuing a rebase, or pushing any conflicted PR. A user's request to choose ours/theirs or force-push does not waive safeguards.

## Investigation order

1. Run `git status` and record each conflicted file.
2. Read the conflict diff and **both sides** of every hunk; identify branch intent and upstream intent.
3. Inspect relevant `git log` / commit history and messages for both sides.
4. Check whether commits or user work appeared after the sweep began.
5. Decide whether the conflict is routine enough to resolve or requires STOP.

Only after this evidence may a routine hunk take branch, upstream, or a manual merge. Upstream may already contain equivalent work, making a rebased commit empty; dropping that empty commit is valid. Preserve both intents when both are required.

## Mandatory STOP

STOP without modifying conflicted files, staging, rebase continuation, or push when any applies:

- substantive architectural logic exists on both sides and the correct combination is ambiguous;
- resolution would remove or overwrite code the user added after the sweep began;
- roughly more than three files or more than 50 manually conflicted LOC require judgment;
- resolution expands into architecture/product policy or exceeds the sweep's routine-fix boundary.

Preserve concurrent user work. Never blindly choose ours/theirs and never overwrite the remote branch to make the conflict disappear.

## Stop report

Give the user enough evidence to adjudicate without repeating discovery:

- conflicted files and approximate conflicted LOC;
- each side's behavior/intent and relevant commit messages;
- user-work or data-loss risk;
- safe options and a recommended decision path;
- PR disposition (`NEEDS FIX`/STOP) and next wakeup.

## After a safe resolution

Verify the merged behavior and relevant tests before push. Default to plain `git push` when history was not rewritten.

`--force-with-lease` is narrowly permitted only after a clean rebase of the **same feature branch against its same upstream**, after fetching and confirming nobody pushed since the expected remote tip. The lease must protect that expected tip. It is not permission to overwrite shared/user work and is never used for a substantive STOP case. Plain `--force` is prohibited in all cases; base branches are never pushed.

Do not narrate housekeeping in review threads unless a thread specifically concerns the conflict.
