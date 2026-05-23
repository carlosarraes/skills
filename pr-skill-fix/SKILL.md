---
name: pr-skill-fix
description: "Handle HUMAN reviewer feedback on the user's open non-draft PRs — the human-comments counterpart to `pr-sweep` (bots). Per PR: APPROVED + non-blocking → score each finding (trivial=fix-here, scope-creep=follow-up ticket), confirm batch once (pushing invalidates approval); CHANGES_REQUESTED + overall body → fix silently, one commit per finding, no reply; CHANGES_REQUESTED + inline threads → one commit per thread, reply with SHA, resolve. After fixes, `ScheduleWakeup` 10 min, rechecks CI, punts new bot activity to `/pr-sweep`, then re-requests review from humans who blocked and posts one summary comment. Linear default, `jira` arg for Jira follow-ups. Trigger on 'fix user comments on PRs', 'address review feedback', 'handle changes requested', 'reply to my reviewer', 'respond to PR review', 'fix and re-request review', '/pr-skill-fix', 'fix reviewer nits', 'turn around review comments', or when the user just got a CHANGES_REQUESTED review."
---

# PR Skill Fix

Drive a batch of open PRs through their **human** reviewer feedback to the point where each PR is either (a) re-requested from the reviewer who blocked it, or (b) intentionally untouched because the comments were filed as follow-up tickets. The loop is self-pacing on ~10 minutes via `ScheduleWakeup`, so it can sit and watch CI + bot follow-up after each push without blocking the user's terminal.

This is the companion to `pr-sweep`, not a replacement. `pr-sweep` knows how to talk to Greptile, Cursor BugBot, and CI. **This** skill knows how to talk to humans — which means it cares about things `pr-sweep` doesn't: that pushing a commit to an APPROVED PR invalidates the approval, that "overall" review bodies are different from inline threads, that some reviewer comments deserve a polite "filed as follow-up" rather than an in-PR fix.

## When this skill is the right tool

Use when the user has 1+ open PRs and any of the following are true:
- A human reviewer left **CHANGES_REQUESTED** (with or without inline threads) and the user wants the requests turned around.
- A human reviewer **APPROVED with non-blocking nits/suggestions** and the user wants someone to triage what's worth fixing in-PR vs filing as a follow-up.
- The user just pushed a fix and wants the loop to watch CI + re-request review automatically when the dust settles.

**Do NOT use** when:
- The findings are all from bots (Greptile, Cursor BugBot, dependabot, copilot, github-actions, coderabbitai) → use `/pr-sweep`. If both human and bot findings exist, this skill handles the humans and recommends `/pr-sweep` for the bot side at the end.
- The PR is still Draft — reviewers usually don't post on drafts, and even if they did, the user probably wants to re-read the feedback themselves first.
- The user wants to *open* a PR (use the project's PR command) or do a one-shot single check (just answer directly).

## Inputs

**Default: process ALL the user's open non-draft PRs that have human review activity.** Run:

```bash
gh pr list --author @me --state open --json number,title,headRefName,baseRefName,isDraft,url
```

For each result with `isDraft=false`, fetch reviews + threads + issue-comments (see step 1 of the loop) and **keep only the PRs where at least one human has left a review or comment that requires action.** PRs with zero human activity are silently dropped — they're not in scope.

The user can narrow scope with an explicit PR list (e.g., `/pr-skill-fix #820 #822`); when they do, use exactly that list. The user can also pass `jira` as an argument (e.g., `/pr-skill-fix jira` or `/pr-skill-fix #820 jira`) to switch the follow-up tracker from Linear (default) to Jira.

A **worktree-path map** is also accepted (same shape as `pr-sweep`):

```
MON-877 → /Users/carraesmb/mondrio/mondrio-platform-mon-877-a11y
```

If no map is given, **auto-derive** the worktree path from the branch name following the `mondrio-platform-<branch>` convention. If the path doesn't exist, `git worktree add <path> <branch>` against the remote tip before applying any fix. Never reuse a worktree that's currently on a different branch.

## Distinguishing human vs bot reviewers

A reviewer is a **bot** if any of the following is true:
- The GitHub user `type` is `Bot` (visible in `gh api repos/<o/r>/pulls/<#>/reviews --jq '.[].user.type'`).
- The login matches the known list: `greptile-apps[bot]`, `cursor[bot]`, `cursoragent[bot]`, `dependabot[bot]`, `copilot[bot]`, `github-actions[bot]`, `coderabbitai[bot]`, `renovate[bot]`, `sonarqubecloud[bot]`.

Everything else is a human. When the type/login is ambiguous, treat as human — false positives here are harmless (the user just sees the comment surfaced).

## The decision tree (memorize this)

Per PR, after filtering to human activity:

| Review state            | Comment form                  | Action                                                                                                  |
|-------------------------|-------------------------------|---------------------------------------------------------------------------------------------------------|
| `APPROVED`              | Inline thread (non-blocking)  | Score per heuristic below → fix-here OR follow-up. **Confirm the whole batch with the user once.**       |
| `APPROVED`              | Overall body comment          | Same heuristic + same single confirmation.                                                              |
| `CHANGES_REQUESTED`     | Overall body only             | Fix silently. One commit per finding. **Do NOT reply** to the review body.                              |
| `CHANGES_REQUESTED`     | Inline review threads         | Fix. One commit per thread. Reply to thread with SHA + one-line explanation. Resolve thread.            |
| `COMMENTED` (no verdict)| Either                        | Treat as APPROVED-style — same heuristic + confirmation.                                                |
| Dismissed / stale       | Either                        | Skip. Note in report.                                                                                   |

The reason CHANGES_REQUESTED + overall body gets no reply: top-level review bodies aren't threadable conversationally on GitHub — the cleanest acknowledgment is the new commit plus the eventual re-request. Replying with "fixed in <sha>" on a top-level review tends to read as noise. The reviewer will see what changed when they open the re-review.

### Heuristic — "fix here" vs "follow-up ticket"

Score each non-blocking comment along these axes and recommend per-comment:

- **Strong "fix here"** — typo, doc nit, rename, missing JSDoc, dead import, single-line refactor, missing null-check on already-touched code, test-name fix. Cheap, in-scope, the reviewer expects it to land.
- **Borderline → lean fix-here** — 1–20 LOC behavioral change in a file the PR already touches, no new tests required.
- **Strong "follow-up"** — new feature surface, multi-file refactor, "while you're here, also do X" scope-creep, architectural change, anything that would expand the PR past the ticket's acceptance criteria, or anything the reviewer themselves prefaced with "non-blocking, but..." / "in a follow-up".

Surface recommendations to the user as **one batched ask**:

```
APPROVED-PR triage — 8 non-blocking comments across PR #820, #822, #831

PR #820 (approved by @alice):
  [fix-here] inline thread: "rename `cfg` to `config` for consistency" → 1-line rename
  [fix-here] overall body: "add a TODO comment explaining the cache TTL"
  [follow-up] inline thread: "while you're here, also refactor the auth layer to use the new SDK"

PR #822 (approved by @bob):
  [fix-here] inline thread: "missing test for the empty-array case"
  [follow-up] overall body: "consider extracting this into a shared util — there are 3 other places that need it"

PR #831 (approved by @alice):
  [fix-here] inline thread: "typo in error message: 'recieved' → 'received'"
  [follow-up] inline thread: "we should add structured logging here in a follow-up"
  [follow-up] inline thread: "long-term we want to migrate this off the old API"

Recommendation: 4 fix-here, 4 follow-up.

Heads up: any fix-here on PR #820 / #822 / #831 invalidates the approval and forces re-review.

Proceed? (yes / no / edit specific items)
```

Wait for the user to confirm before dispatching fix agents on APPROVED PRs. CHANGES_REQUESTED PRs do **not** require this confirmation — they're blocking, so fixing them is the entire point.

## The loop, one full iteration

### Step 1: Gather state for every in-scope PR (in parallel)

For each PR, run these queries in parallel:

**Reviews** (latest verdict per reviewer):
```bash
gh api "repos/<o/r>/pulls/<#>/reviews" \
  --jq '[.[] | {user: .user.login, type: .user.type, state, body, submitted_at}]
        | group_by(.user)
        | map(sort_by(.submitted_at) | last)'
```
Keep only entries where `type != "Bot"` and the login isn't in the bot list above.

**Inline threads** — GraphQL, same shape as `pr-sweep` but filter the first comment's author:
```bash
gh api graphql -f query='query{
  repository(owner:"<owner>", name:"<repo>") {
    pullRequest(number: <#>) {
      reviewThreads(first: 50) {
        nodes {
          id isResolved
          comments(first: 1) {
            nodes { author { login } bodyText databaseId }
          }
        }
      }
    }
  }
}'
```
Drop threads whose first comment's author is a bot (per the bot rules above). Drop resolved threads. What's left is the human-inline-thread queue.

**Issue-level comments** (top-level PR comments that aren't part of a review):
```bash
gh api "repos/<o/r>/issues/<#>/comments" \
  --jq '[.[] | select(.user.type != "Bot") | {id, user: .user.login, body, created_at}]'
```
These are rarer but real — sometimes reviewers leave a top-level comment instead of a formal review.

**CI status** — copy the latest-per-name pattern verbatim from `pr-sweep`:
```bash
sha=$(gh pr view <#> --repo <o/r> --json headRefOid -q .headRefOid)
gh api "repos/<o/r>/commits/$sha/check-runs?per_page=100" --jq '.check_runs
  | group_by(.name)
  | map(sort_by(.started_at) | last)
  | .[]
  | select(.conclusion != "success" and .conclusion != "neutral" and .conclusion != "skipped")
  | "\(.status)/\(.conclusion // "running") — \(.name)"'
```
The `group_by(.name) | map(sort_by(.started_at) | last)` is load-bearing — it filters out historical failures.

### Step 2: Classify each PR

Apply the decision table. Bucket findings per PR into one of four lists:
- `inline-fix-reply` (CHANGES_REQUESTED inline, OR APPROVED inline + fix-here)
- `overall-silent` (CHANGES_REQUESTED overall body)
- `approved-fix-here-overall` (APPROVED overall + fix-here decision)
- `follow-up-ticket` (APPROVED + follow-up decision, either form)

Skip PRs with empty buckets this cycle.

### Step 3: Confirm with the user (APPROVED batches only)

If any PR has non-empty `approved-fix-here-overall` or `follow-up-ticket` or APPROVED-inline buckets, surface the triage and wait for confirmation. CHANGES_REQUESTED PRs proceed without asking.

If the user says "edit", let them flip individual items between fix-here and follow-up, then re-confirm.

### Step 4: Dispatch fix agents in parallel

For each PR with at least one actionable bucket, dispatch one `Agent` (subagent_type `general-purpose`) with:
- Exact worktree path.
- The bucketed findings (each thread carries its `databaseId` for inline, its `id` for the GraphQL `resolveReviewThread` mutation, and the reviewer's login for the follow-up ticket body).
- The fix protocol (next section).
- The follow-up tracker (`linear` or `jira`) and the ticket-of-origin ID extracted from the branch name.

One agent per PR. PRs are independent (separate worktrees) so parallel is safe.

### Step 5: Re-arm the loop — DO NOT SKIP

**Unconditionally** call `ScheduleWakeup` for ~600 seconds (10 minutes) with the same loop prompt, except when **every** in-scope PR has reached the terminal state (see step 7). If you forget, the loop dies silently — the same trap as `pr-sweep`.

Treat the `ScheduleWakeup` call as the closing brace of the iteration. Write it before you start composing the iteration report so muscle memory doesn't betray you.

### Step 6: Report iteration (under 300 words)

Per-PR status table, what was fixed / filed this cycle, what's still pending, next wakeup ETA (or `DONE`).

### Step 7: On the next firing — recheck, re-request, or re-loop

When the wakeup fires, re-run step 1 for the PRs that had fixes pushed last cycle. Then for each:

- **CI broken by our fix** → treat as CHANGES_REQUESTED-style: investigate, fix, push, loop again.
- **New human comments since last fix** → fold into the next iteration's classify-and-dispatch.
- **New bot comments since last fix** → **do not handle here.** Surface a one-line "bot follow-up detected on PR #N — run `/pr-sweep #N`" and proceed. Splitting responsibility keeps both skills predictable.
- **Clean** (CI green, no new human activity, all original threads resolved or filed) → **re-request review**:
  ```bash
  gh api -X POST "repos/<o/r>/pulls/<#>/requested_reviewers" \
    -f reviewers='["<login>", ...]'
  ```
  for each human reviewer whose latest verdict was `CHANGES_REQUESTED`. (Don't re-request from approvers — they already approved; pushing fix-here commits invalidated their approval, but GitHub auto-re-requests in that case.)

  Then post one PR-level summary comment:
  ```bash
  gh pr comment <#> --body "$(cat <<'EOF'
  Re-requesting review — addressed feedback in:

  - <sha1> <commit subject>
  - <sha2> <commit subject>
  ...

  Filed as follow-up:
  - <ticket-url> <follow-up summary>
  EOF
  )"
  ```
  This gives the reviewer a one-glance "here's what changed since you last looked" handoff so they're not hunting through the commit list.

A PR is in the **terminal state** when re-request has fired AND there's no new human activity OR when all original findings were resolved via follow-up tickets (no commits, no re-request needed).

## The fix protocol (what each fix agent does)

The agent receives the worktree path, bucketed findings, follow-up tracker choice, and these instructions:

1. **`cd` into the worktree** and stay there. Auto-derive the path if not provided; create the worktree with `git worktree add <path> <branch>` if it doesn't exist.

2. **Pull latest**: `git pull --rebase`. If the LFS-pointer dance blocks it (the `backend/tests/fixtures/surveys/*.json` issue this repo has), run `git update-index --assume-unchanged backend/tests/fixtures/surveys/*.json` before pulling. Restore with `--no-assume-unchanged` at the end if you can.

3. **Inline-fix-reply** (per thread): apply the smallest correct fix. **One commit per thread**, Conventional Commits: `<type>(<scope>): <description> (TICKET-ID)` where TICKET-ID comes from the branch name. Push (`git push`, no force). Then reply and resolve:
   ```bash
   gh api -X POST "repos/<o/r>/pulls/<#>/comments/<databaseId>/replies" \
     -f body="Fixed in <SHA>. <one-line explanation>"
   gh api graphql -f query='mutation{
     resolveReviewThread(input: {threadId: "<thread-id>"}) { thread { isResolved } }
   }'
   ```

4. **Overall-silent** (CHANGES_REQUESTED overall body): split the requested changes into discrete fixes — **one commit per requested change**, so the reviewer can scan commit-by-commit. Push. **No reply to the review body.** The eventual re-request comment is the response.

5. **Approved-fix-here-overall** (APPROVED + APPROVED-overall + fix-here): apply each finding as its own commit and push. No thread reply needed for top-level approval comments. Note in the agent's report: "approval invalidated on PR #N, GitHub will auto-mark @reviewer as pending re-review."

6. **Follow-up-ticket**: do **not** modify the PR. Create a ticket in the chosen tracker (`linear` or `jira`):
   - **Linear** (default) — use the `mcp__claude_ai_Linear__save_issue` MCP tool. Title: `Follow-up: <short summary>`. Body: quote the reviewer's comment verbatim, link the PR, name the origin ticket. Use the same team as the origin ticket if you can determine it from the branch; otherwise the agent's default team.
   - **Jira** — use the project's standard Jira CLI/MCP path. Same title and body shape.

   Then reply once:
   - If the comment was inline → reply to the thread with `Filed as follow-up: <ticket-url>` and resolve the thread.
   - If the comment was an overall body → post one PR-level comment via `gh pr comment <#> --body "Filed as follow-up: <ticket-url> (re: @reviewer's note about ...)"`.

7. **Verify before pushing**: `tsc --noEmit` (frontend) or `uv run pyright && uv run ruff check .` (backend). Don't push code that breaks type-check or lint.

8. **PR title fixes**: if a reviewer's comment is about the PR title (rare, but happens), edit via `gh pr edit <#> --title "..."` rather than committing.

## Resolving merge conflicts during the loop

Same investigation order and patterns as `pr-sweep` (read both sides, prefer empty-commit-drop over speculative merges, manual merge when both sides changed the same area for different reasons). The STOP criteria are the same: >3 conflicting files, >50 LOC of conflict, or architectural ambiguity. STOP means: report the conflict in detail to the loop and let the user decide.

## Pushback-worthy comments (from humans, not bots)

Humans are usually more right than bots, but not always. The agent **may** push back (politely, then resolve the thread) when:

- The reviewer's suggestion contradicts an explicit pattern documented in the repo's CLAUDE.md or in `prep-ticket` notes for the ticket — cite the line.
- The suggestion would expand the PR past the ticket's acceptance criteria. Defer with "Filed as follow-up: <ticket-url>" and resolve.
- The suggestion is technically incorrect (e.g., asks for a refactor that would break a tested invariant). The reply must cite the failing test or the invariant. Resolve only if the agent is confident.

Pushback only works when the reply is specific and grounded in artifacts the reviewer can verify. A weak defer will get reopened. When in doubt, **don't push back** — just file as follow-up and let the user adjudicate.

## Constraints — non-negotiable

- **Never bypass hooks** with `--no-verify`. The hook's complaint is part of the fix.
- **Never push to `develop`, `main`, or any base branch.** Feature branches only.
- **Default to plain `git push`.** Force-push only if a rebase landed cleanly and the upstream is the same branch — use `--force-with-lease`, never `--force`.
- **Never dismiss a reviewer's review.** Even if you think they were wrong, surface to the user; don't programmatically dismiss.
- **Never re-request review from a reviewer who is on PTO / out-of-office** if you can detect it (the user will tell you in chat if relevant — otherwise proceed).
- **STOP instead of patching** if a finding requires:
  - More than ~100 LOC of code change.
  - An architectural decision ("should this hook be split?").
  - A product call ("should this UX behave this way?").
  - Touching code outside the PR's existing diff scope by more than a small adjacent fix.

  STOP means: surface the finding back to the loop with a recommended path, and let the user decide.

## Edge cases worth knowing about

- **Approval-then-changes_requested by the same reviewer**: GitHub keeps the latest verdict. If @alice approved on commit A and then requested changes on commit B, treat the PR as CHANGES_REQUESTED. Don't fold the earlier approval into the heuristic batch.
- **Multiple reviewers in different states**: e.g., @alice approved + @bob requested changes. Handle the changes-requested findings under the blocking protocol; handle alice's nits (if any) under the heuristic protocol. Re-request review from @bob when done — not @alice.
- **Reviewer comments on a PR you already retitled**: title-change re-fires the conventional-commits check but does NOT dismiss reviews. Reviews persist across title edits.
- **Stacked PRs**: PR B's base is PR A's branch. Same caveat as `pr-sweep` — when A merges, B needs `gh pr edit <B> --base develop` (or whatever the real base is). Surface this in the final report; don't auto-retarget.
- **Reviewer asked for a follow-up explicitly**: if the comment itself says "let's do this in a follow-up", treat as `follow-up-ticket` regardless of size — the reviewer told you the answer.
- **Reviewer asked you NOT to file a follow-up**: e.g., "this is just a thought, don't bother filing". Recognize this and skip both fix and ticket-creation; just reply "Noted, thanks" and resolve.
- **Empty `requested_reviewers` POST**: GitHub silently no-ops if the reviewer is already in the requested list. Safe to call defensively.

## Final DONE report

When every in-scope PR is in the terminal state:

1. Don't reschedule.
2. Per-PR final table: PR#, commits added during the loop, threads resolved/replied, follow-up tickets filed (with links), re-request status, any deferrals.
3. Call out:
   - Any stacked-PR retargets needed.
   - Any bot follow-up that appeared mid-loop and was punted to `/pr-sweep`.
   - Any STOPs that need user adjudication.
4. List the follow-up tickets created — these are the most valuable byproduct, since they capture reviewer wisdom that didn't fit in the current PR.

## Iteration cadence — why 10 minutes

Same reasoning as `pr-sweep`: 10 minutes amortizes the Anthropic prompt-cache miss (5-minute TTL), gives CI runs (5–7 min) time to complete a full cycle, and respects the rhythm humans actually re-review at — they're not refreshing the PR every 30 seconds. 5 minutes is too tight (cache thrash + nothing has finished); 30 minutes loses the rhythm. Stay between 5 and 20 unless the user requests otherwise.
