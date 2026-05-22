---
name: pr-sweep
description: "Monitor every open non-draft PR by the user on a 10-minute loop and auto-fix CI failures, merge conflicts, and bot review comments (Greptile, Cursor BugBot) until every PR is simultaneously green, conflict-free, and has zero unresolved threads. By default sweeps ALL the user's open PRs via `gh pr list --author @me`; an explicit PR list narrows the scope. Use this skill whenever the user asks to 'sweep PRs', 'sweep my PRs', 'monitor my PRs', 'watch CI + bots', 'fix bot review comments', 'babysit my PRs until they're clean', 'handle Greptile/Cursor findings', 'resolve PR conflicts', '/pr-sweep', or whenever the user has just flipped one or more PRs from Draft to Ready and wants automated handling of the bot feedback that will arrive over the next hour. Also trigger on 'run the loop', 'check my PRs every 10 minutes', 'don't stop until all the bots are happy'. The skill schedules itself via ScheduleWakeup so it survives across many cycles."
---

# PR Sweep

Drive a batch of open PRs to a clean state — every CI check green, every Greptile/Cursor BugBot thread resolved — by running a self-pacing 10-minute loop that detects issues, dispatches minimal fixes, and re-arms itself until done.

This skill is most useful right after a batch of PRs flip from Draft to Ready, because that's when the review bots start posting and CI starts running. The bots take roughly 5–12 minutes to post their first round, so the cadence is: wait 10 min, sweep, fix, repeat.

## When this skill is the right tool

Use when the user has 1+ open PRs and wants any of:
- CI failures handled (real fixes + flake reruns)
- Greptile / Cursor BugBot findings replied + resolved
- A "wake me when everything's clean" loop, not blocking the user's terminal

**Do NOT use** when:
- The user asks to *open* a PR (use `/be-pr` / `/frontend-pr`)
- The user wants a one-shot single check, not a loop
- The PRs are still Draft — bots won't post until Ready

## Inputs

**Default: sweep ALL the user's open PRs.** Run:

```bash
gh pr list --author @me --state open --json number,title,headRefName,baseRefName,isDraft
```

Include every result whose `isDraft` is `false`. Draft PRs are excluded because Greptile and Cursor BugBot don't review drafts — there's nothing to sweep there. If the count is unexpectedly large (>8) or includes PRs from unrelated repos, confirm with the user once before proceeding.

The user can still narrow the scope by passing an explicit PR list (e.g., `/pr-sweep #820 #822`). When they do, use exactly that list and skip the `gh pr list` call.

Also accept (optional) a **worktree-path map**, e.g.:
```
MON-877 → /Users/carraesmb/mondrio/mondrio-platform-mon-877-a11y
MON-876 → /Users/carraesmb/mondrio/mondrio-platform-mon-876-sort
```

If no map is given, **auto-derive** the worktree path from the branch name. The convention this repo uses is `mondrio-platform-mon-<NUM>-<slug>`, but if the path doesn't exist, create a fresh worktree with `git worktree add <path> <branch>` (against the remote tip) before applying any fix. Don't reuse an existing worktree that's on a different branch.

## The loop, one full iteration

This is the heart of the skill. Follow it exactly — the order matters because re-scheduling has to happen unconditionally at the end.

### Step 1: Sweep all PRs in parallel

For each PR, run two queries in parallel (one Bash call per PR is fine):

**CI check status** — use the API, not `gh pr checks --json`. The latter exits non-zero whenever anything is non-success, which breaks shell pipelines:

```bash
sha=$(gh pr view <#> --repo <owner/repo> --json headRefOid -q .headRefOid)
gh api "repos/<owner/repo>/commits/$sha/check-runs?per_page=100" --jq '.check_runs
  | group_by(.name)
  | map(sort_by(.started_at) | last)
  | .[]
  | select(.conclusion != "success" and .conclusion != "neutral" and .conclusion != "skipped")
  | "\(.status)/\(.conclusion // "running") — \(.name)"'
```

The `group_by(.name) | map(sort_by(.started_at) | last)` is load-bearing — it filters out **historical** failures from before a retitle or rebase. A PR whose latest run is green but whose history contains a failed run should be treated as green; otherwise the loop will chase fixes for problems that no longer exist.

**Unresolved review threads** — use the GraphQL API:

```bash
gh api graphql -f query='query{
  repository(owner:"<owner>", name:"<repo>") {
    pullRequest(number: <#>) {
      reviewThreads(first: 50) {
        nodes { id isResolved comments(first: 1) { nodes { author { login } bodyText databaseId } } }
      }
    }
  }
}'
```

Pipe through a small Python filter that keeps only `isResolved: false` entries and prints `thread_id | author | databaseId | bodyText[:200]`. The `databaseId` from the first comment in the thread is what you POST replies to; the `id` (a `PRRT_kw...` token) is what you pass to `resolveReviewThread`.

### Step 2: Decide per-PR

For each PR, classify:

- **DONE** — all checks pass (latest-per-name) AND zero unresolved threads.
- **NEEDS FIX** — at least one failing check OR at least one unresolved bot thread.
- **WAITING** — checks include `in_progress/running` items (Cursor BugBot, e2e shards) but nothing failing, and threads are clean. Treat as "not done yet" but don't dispatch a fix; the next iteration will recheck.

The loop stops only when ALL PRs are DONE simultaneously.

### Step 3: Dispatch fixes for NEEDS FIX PRs (in parallel)

For each PR with findings, dispatch one fix agent (Agent tool, `general-purpose`). Give each agent:

- The exact worktree path
- The full set of findings for its PR (thread IDs + bodies + databaseIDs, failing check details)
- The fix protocol below

Parallel is fine because each PR's worktree is independent. Don't dispatch more than one agent per PR per iteration.

### Step 4: Re-arm the loop — CRITICAL

**Before finishing your reply, call `ScheduleWakeup` for ~10 minutes (600 seconds) with the same loop prompt.** If you skip this step, the loop dies silently — there's no error, just silence after the next 10 minutes pass.

This bites hard because it's easy to forget after dispatching the fix agents (the active work feels like the "real" output). The skill is worthless without the reschedule, so treat it as the closing brace of the iteration.

The only time you DON'T reschedule is when **every** PR is DONE and you're reporting the final terminating state.

### Step 5: Report iteration

Under 300 words. A status table per PR + what was fixed this cycle + next wakeup ETA (or `DONE`).

---

## The fix protocol (what each fix agent does)

The agent receives the worktree path, the findings, and these instructions:

1. **CD into the worktree** and stay there.
2. **Pull latest**: `git pull --rebase`. If the LFS-pointer dance blocks it (Mondrio has stale LFS pointer files in `backend/tests/fixtures/surveys/*.json` that show as modified in every worktree), run:
   ```bash
   git update-index --assume-unchanged backend/tests/fixtures/surveys/*.json
   ```
   before pulling. Restore with `--no-assume-unchanged` at the end if you can; it's not critical.
3. **For each failing CI check**: investigate via `gh run view <run-id> --log`. Two outcomes:
   - **Flake** (failures in tests unrelated to the PR's diff scope) → `gh run rerun <run-id> --failed`. Don't fix code for flakes. Confirm the flake hypothesis by correlating the failing test files against the PR's `git diff --name-only` output — if no overlap, it's almost certainly a flake.
   - **Real failure** → fix the underlying code, add a regression test if you can.
4. **For each unresolved bot thread**:
   - Read the body carefully. The thread categories that matter:
     - Greptile findings about code-convention violations (stale ticket refs, missing tests, structural issues)
     - Cursor BugBot findings about real bugs (state leaks, type-safety gaps, race conditions, defensive-contract holes)
     - Greptile / Cursor refactor *suggestions* that may not be worth following — see "Pushback-worthy threads" below
   - Apply the smallest correct fix. One commit per finding, Conventional Commits (`<type>(<scope>): <description> (MON-XXX)`), where the ticket suffix is extracted from the branch name.
   - Push the commit (plain `git push`, no force unless the branch was rebased).
   - Reply to the thread with the fix SHA:
     ```bash
     gh api -X POST "repos/<owner/repo>/pulls/<#>/comments/<databaseId>/replies" \
       -f body="Fixed in <SHA>. <one-line explanation>"
     ```
   - Resolve the thread:
     ```bash
     gh api graphql -f query='mutation{
       resolveReviewThread(input: {threadId: "<thread-id>"}) { thread { isResolved } }
     }'
     ```
5. **Verify before pushing**: `tsc --noEmit` (frontend) or `uv run pyright && uv run ruff check .` (backend). Don't push code that breaks type-check.
6. **PR title fixes**: if the failing check is `Conventional Commits` and the issue is the PR title (e.g., `gh pr view <#> --json title` shows uppercase after the colon), edit via `gh pr edit <#> --title "..."`. Title changes auto-trigger the check; no code commit needed.

## Resolving merge conflicts during the loop

Conflicts surface in two places:

1. **At `git pull --rebase`** in a worktree, when the remote branch picked up new commits the loop didn't make (e.g., the user or another session pushed work to the same branch).
2. **In `gh pr checks` as a `Mergeability` failure** (or via `gh pr view <#> --json mergeable -q .mergeable` returning `CONFLICTING`) when the PR's base branch (typically `develop`) has moved on and the PR no longer fast-forwards cleanly.

Both cases are resolvable in the loop. The agent must investigate before resolving; "take ours" or "take theirs" without understanding which side has the right code is how PRs land regressions.

### Investigation order

1. `git status` — confirm what's conflicting.
2. `git diff` on each conflicting file — read both sides of the `<<<<<<<` / `=======` markers.
3. `git log --oneline <conflicting-commit-range>` — see what each side did and why.
4. For each conflicted hunk, decide:
   - **Take ours (the branch's version)** — when the branch's change is the substantive feature work and the upstream change is a refactor that the branch can absorb.
   - **Take theirs (the upstream version)** — when the upstream already did the work the branch was trying to do (common when a parallel PR landed the same change first). Often results in the branch's commit becoming **empty** — that's OK, drop the empty commit (`git rebase --skip` or `--allow-empty=drop`).
   - **Manual merge** — when both sides changed the same area for different reasons and both need to land. Combine them by hand.
5. After resolving each file: `git add <file>`, then `git rebase --continue`.

### Concrete patterns from real runs

- **Empty commit after upstream did the same work**: the branch's commit was "unify `TierConfig` import," but upstream landed that exact change first. Resolution: take upstream's version, the commit drops as empty during rebase, branch ends up 1 commit shorter — that's a *good* outcome, the work was duplicated.
- **Cherry-pick conflict on a format-only commit**: when splitting a branch into stacked PRs, a `style:` commit may want to format files that aren't on the new branch yet (because they're part of the stacked half). Resolution: `git rm` the missing files from the cherry-pick — they get re-added cleanly by a later commit in the stack.
- **Mid-loop push from user**: agent's pull --rebase shows the branch has 6 unknown commits. Don't clobber them with `--force-with-lease` — rebase the loop's chaos/fix commits ON TOP of the upstream work. The user's intent was to expand the branch, not for the agent to overwrite it.

### When to STOP instead of resolve

- The conflict is in a file the agent doesn't understand the architecture of, AND a `git log` of both sides shows substantive logic from each. (Don't guess on architectural merges.)
- The conflict involves removing code that the user explicitly added in a commit since the loop started — the user probably intended that code to stay.
- More than ~3 conflicting files OR more than ~50 LOC of conflict to resolve manually. That's signal the branches have drifted too far for a routine sweep; surface to the user.

STOP means: report the conflict in detail (files, both sides of the diff, both sides' commit messages) and let the user decide.

### After conflict resolution

- Push with plain `git push` (not `--force`) if the rebase was clean and the upstream is the same branch you pulled from.
- If the rebase rewrote shared commits, push with `--force-with-lease`, NEVER plain `--force`. `--force-with-lease` aborts if someone else pushed between your last fetch and now — that safety check has saved real work.
- Don't comment on PR threads about the rebase unless a thread is specifically asking about it. The loop's job is to close threads, not narrate housekeeping.

## Pushback-worthy threads

Not every bot suggestion is worth implementing. The agent should defer with a thoughtful reply (then resolve the thread) when:

- **The suggested refactor would add a 4th copy of logic that already exists in 2-3 utility modules.** Document the right unification path as a follow-up ticket; don't add the 4th.
- **The suggested rule isn't actually a team convention** (e.g., "store mocks in dedicated `mocks/` subdirectory" when the team's own tests co-locate helpers in test files). Cite an existing file as precedent.
- **The change would expand PR scope past the ticket's acceptance criteria.** Defer with "out of scope, filed as follow-up."

Pushback only works when the reply is specific (cites a precedent file, names a follow-up ticket) and the agent has actually looked at the code, not just defended on principle. A weak defer ("we don't do that here") will get reopened by the reviewer.

## Constraints — non-negotiable

- **Never bypass hooks** with `--no-verify`. If a hook fails, the fix the hook flagged is the real fix.
- **Never push to `develop` or `main`**. Feature branches only.
- **Never force-push** (`--force`, `--force-with-lease`) unless a rebase landed cleanly and the upstream is the same branch. The agent should default to plain `git push`.
- **Stop instead of patching** if a finding requires:
  - More than ~100 LOC of code change
  - An architectural decision (e.g., "should this hook be split?")
  - A product call (e.g., "should this UX behave this way?")

  STOP means: report back to the loop with the finding's details and what you would have done. The user decides next.

## Edge cases worth knowing about

- **Stacked PRs**: PR B's base is PR A's branch (not `develop`). After A merges, B needs to be retargeted with `gh pr edit <B> --base develop`. The sweep handles stacked PRs fine; just remember to flag the retarget in the final DONE report.
- **PR title validation failures**: the `action-semantic-pull-request` check enforces lowercase first word after the colon. If the title starts with a ticket ID (`MON-1096`) or an acronym (`PR-review`), it fails. Title-edit re-fires the check; no code change required.
- **Brand-new bot threads after a fix**: each push can surface new findings as the bot re-reviews. Don't be surprised if iteration N+1 shows new threads on the very files iteration N fixed — that's normal. Treat them as fresh findings.
- **Cursor BugBot still `in_progress`**: if all threads are clean but Cursor is mid-review, don't declare DONE. Wait one more cycle.
- **Bots replying to their own threads**: occasionally Greptile/Cursor will follow up on a thread the agent already resolved (e.g., "agreed, but consider also X"). Treat as a new finding only if the follow-up is asking for additional code change.

## Final DONE report

When the stopping condition is met:

1. Don't reschedule.
2. Report a per-PR final table: PR#, commits added during the loop, threads resolved, any deferrals.
3. Call out any stacked-PR retargets needed.
4. Surface any follow-up tickets the agents identified during pushback or defer decisions (these are the most valuable insights the loop produces — they tell the user about tech debt the bots noticed but didn't have authority to fix).

## Iteration cadence — why 10 minutes

The number isn't arbitrary. Reasons:

- Greptile and Cursor BugBot post the first round 5–12 minutes after Ready-flip. A 5-minute cadence would miss the bot's first pass; a 30-minute cadence wastes wall-clock.
- The Anthropic prompt cache has a 5-minute TTL. Below 5 minutes, the conversation context stays cached (cheap). Above 5 minutes, the next iteration pays a cache miss anyway, so amortize it — 10 minutes is past the miss and lets bots do meaningful work.
- CI runs (e2e shards in particular) take 5–7 minutes. A 10-minute gap typically catches one full run cycle.

If a sweep is being done on a project where the bots are faster or slower, adjust to taste — but don't go below 5 minutes (cache thrash) or above 20 minutes (loop loses its rhythm).
