---
name: pr-sweep
description: "Use when the user wants their open non-draft PRs driven to a clean, mergeable state: CI/pipeline green, merge conflicts resolved, size gate satisfied, and every review thread (bot AND human) resolved or turned around. Covers Greptile findings (inline threads + the summary comment's confidence score and T-Rex runtime logs) / Cursor BugBot, CI failures and flakes, the Mondrio PR size gate, inline review threads, and top-level 'changes requested' review bodies (one big comment listing fixes). Triggers: 'sweep my PRs', 'monitor my PRs', 'watch CI + bots', 'fix bot/review comments', 'handle Greptile/Cursor findings', 'resolve PR conflicts', 'address review feedback', 'handle changes requested', 'reply to my reviewer', 'fix and re-request review', 'babysit my PRs', '/pr-sweep', or just flipped PRs Draft to Ready. Sweeps all the user's open PRs (gh pr list --author @me); explicit list narrows scope; pass 'jira' for Jira follow-ups (Linear default)."
---

# PR Sweep

Drive a batch of open PRs to a clean, mergeable state — every CI check green, every merge conflict resolved, the size gate satisfied, every review thread (Greptile, Cursor BugBot, **and** human) resolved, and every blocking human review turned around — by running a self-pacing ~10-minute loop that detects issues, dispatches minimal coordinated fixes, and re-arms itself until done.

This skill is most useful right after a batch of PRs flip from Draft to Ready, because that's when the review bots start posting, CI starts running, and human reviewers start looking. The bots take ~5–12 minutes to post their first round; humans arrive on their own schedule. The cadence absorbs both: wait ~10 min, sweep, fix, repeat.

**One skill, not two.** Earlier versions split this into `pr-sweep` (bots + CI) and `pr-sweep-fix` (humans). That seam was wrong: the thing that changes the handling isn't *who* left the feedback, it's **where it lives** (a CI check, an inline thread, or a top-level review body) and **what state the review is in** (approved vs changes-requested). Fixing a Greptile inline thread and fixing a human inline thread are mechanically identical. Splitting by author also made the two loops *race* — each pushed its own commits, each invalidating approvals and re-triggering CI + bots. This skill handles every kind of feedback for a PR in **one coordinated pass per PR per cycle**, pushing once.

## When this skill is the right tool

Use when the user has 1+ open non-draft PRs and wants any of:
- CI failures handled (real fixes + flake reruns)
- Merge conflicts resolved
- The Mondrio size gate satisfied (override-or-split)
- Greptile / Cursor BugBot findings replied + resolved
- Human review feedback turned around — `CHANGES_REQUESTED` fixed, approved-PR nits triaged, reviewers re-requested
- A "wake me when everything's clean" loop, not blocking the user's terminal

**Do NOT use** when:
- The user asks to *open* a PR (use `/be-pr` / `/frontend-pr` / the project's PR command)
- The user wants a one-shot single check, not a loop (just answer directly)
- The PRs are still Draft — bots don't review drafts, and reviewers usually don't either; the user probably wants to re-read feedback themselves first

## Inputs

**Default: sweep ALL the user's open non-draft PRs.** Run:

```bash
gh pr list --author @me --state open --json number,title,headRefName,baseRefName,isDraft,url
```

Include every result whose `isDraft` is `false`. Draft PRs are excluded — neither Greptile, Cursor BugBot, nor most reviewers post on drafts, so there's nothing to sweep. If the count is unexpectedly large (>8) or includes PRs from unrelated repos, confirm with the user once before proceeding.

The user can narrow scope by passing an explicit PR list (e.g., `/pr-sweep #820 #822`). When they do, use exactly that list and skip the `gh pr list` call.

The user can also pass `jira` as an argument (e.g., `/pr-sweep jira` or `/pr-sweep #820 jira`) to switch the **follow-up tracker** from Linear (default) to Jira.

Also accept (optional) a **worktree-path map**, e.g.:
```
MON-877 → /Users/carraesmb/mondrio/mondrio-platform-mon-877-a11y
MON-876 → /Users/carraesmb/mondrio/mondrio-platform-mon-876-sort
```

If no map is given, **auto-derive** the worktree path from the branch name. The convention this repo uses is `mondrio-platform-mon-<NUM>-<slug>`, but if the path doesn't exist, create a fresh worktree with `git worktree add <path> <branch>` (against the remote tip) before applying any fix. Don't reuse an existing worktree that's on a different branch.

## Distinguishing human vs bot reviewers

The handling is the same for inline threads regardless of author, but a few sub-decisions (the confirm gate, fix-here-vs-follow-up triage, the pushback bar, re-requesting review) depend on it. A reviewer is a **bot** if any of the following is true:
- The GitHub user `type` is `Bot` (visible in `gh api repos/<o/r>/pulls/<#>/reviews --jq '.[].user.type'`).
- The login matches the known list: `greptile-apps[bot]`, `cursor[bot]`, `cursoragent[bot]`, `dependabot[bot]`, `copilot[bot]`, `github-actions[bot]`, `coderabbitai[bot]`, `renovate[bot]`, `sonarqubecloud[bot]`.
- The comment body carries the `🤖 Automated comment by` header — even when posted from a plain `User` account. Skills like `review-swarm` and `qa-pr` post through the user's own account, so the header, not the account, is what marks them automated. A thread opened by a header-marked comment gets **bot** handling (fix or pushback + resolve); a human replying inside it makes the thread human per the usual rules.

Everything else is a human. When the type/login is ambiguous, treat as human — false positives here are harmless (the user just sees the comment surfaced and triaged).

## The model: feedback **form** × review **state**

Every finding is classified along two axes. This matrix is the heart of the skill — Step 2 fills it in, the fix protocol acts on it.

| Layer (form) | Source | State / condition | Handling | Reply | Confirm first? |
|---|---|---|---|---|---|
| **L1** | CI check failing — real | — | fix code + regression test | n/a | no |
| **L1** | CI check failing — flake | — | `gh run rerun --failed` | n/a | no |
| **L1** | `PR Size Gate` failing | — | override **or** recommend split | comment if override | no* |
| **L1** | Conventional Commits / title | — | `gh pr edit --title` | n/a | no |
| **L1** | `Mergeability` / conflict | — | resolve, or STOP | n/a | no |
| **L2** | Inline thread — **bot** | — | smallest fix, OR pushback | reply SHA + resolve | no |
| **L2** | Inline thread — **human** | PR `CHANGES_REQUESTED` (blocking) | fix | reply SHA + resolve | no |
| **L2** | Inline thread — **human** | PR `APPROVED`/`COMMENTED` (non-blocking) | triage → fix-here or follow-up | SHA+resolve, or "filed"+resolve | **YES (batch)** |
| **L3** | Greptile summary comment — **bot** | `Confidence Score` + `T-Rex Logs` | cross-check vs L2 threads → fix **summary-only** findings | **NO reply** | no |
| **L3** | Overall review body — **human** | `CHANGES_REQUESTED` | fix, one commit per item | **NO reply** | no |
| **L3** | Overall review body — **human** | `APPROVED`/`COMMENTED` | triage → fix-here or follow-up | none (fix) / one PR comment (follow-up) | **YES (batch)** |

\* The size-gate override is autonomous, but it's a *policy action* — surface it in every report so the user can review or split later.

Two things fall out of the matrix and are the whole reason the human/bot distinction still matters at all:
- **Approval is fragile, so protect it.** Pushing **any** commit to an `APPROVED` PR invalidates that human's approval and forces re-review. So the gate is keyed on the *approval*, not on who wrote the finding: any **avoidable** push to an approved PR (a nit, a bot suggestion, even a bot bug-fix — anything not strictly required to make the PR mergeable) waits behind a single batch confirmation (Step 3). Only a **merge-required** fix (a real CI failure, a conflict) pushes to an approved PR without asking, and only when it's the *only* work on that PR — and even then, surface it in the report, since it costs the approval. *This overrides the per-row "Confirm first?" column above:* on an approved PR even a bot-thread code-fix waits; on a non-approved PR nothing waits.
- **Top-level review bodies aren't threadable.** A `CHANGES_REQUESTED` overall body gets **no reply** — the cleanest acknowledgment is the new commits plus the eventual re-request. Inline threads, by contrast, always get a reply + resolve.

## The Greptile summary comment (confidence score + T-Rex logs)

Greptile's first post on every PR is a **top-level issue comment** (not a review body — that's empty), with three parts:

- **Greptile Summary** — what the PR does. Context, not action.
- **Confidence Score: N/5** + reasoning — Greptile's merge-readiness verdict, often naming the one blocking concern and its file ("…should be corrected before merging — `backend/src/shared/config.py`"). The score is a **triage signal**, not a gate: a low score means scrutinize harder, but it never *by itself* blocks DONE — resolving the underlying findings does.
- **🦖 T-Rex Logs** ("What T-Rex did") — Greptile *ran* the code in a harness and reports runtime observations. Some are pass-confirmations (no action); some are real findings (a value over a documented cap, a non-zero exit, an override that didn't take effect).

**The one rule: cross-check, don't double-fix.** The score reasoning and T-Rex logs are a *rollup*. A concern Greptile could pin to a line **also** appears as an inline thread (L2) — handle it there, once. A **summary-only** concern (named in the score reasoning or T-Rex logs with no matching inline thread — typically runtime or cross-file) is a fresh bot finding: smallest correct fix (or push back per **Pushback-worthy findings**), one commit, **no reply** — the summary isn't threadable, so the fix commit is the acknowledgment. Never reply to or "resolve" the summary comment, and never make a second commit for what an inline thread already covers. The "View all artifacts" / "Fix all in Claude" buttons are UI affordances — work from the comment text. Surface the score per PR in the report.

## Sweep state — skip quiet PRs

State lives in `~/.local/state/pr-sweep/state.json`, keyed by PR URL:

```json
{
  "https://github.com/mondrio/mondrio-platform/pull/820": {
    "updated_at": "2026-07-12T17:05:00Z",
    "head_sha": "abc123",
    "ci_conclusion": "success",
    "last_comment_at": "2026-07-12T17:00:00Z"
  }
}
```

A PR is **quiet** — skip all its Step 1 per-PR queries this cycle — when its `updatedAt` from the listing call matches the stored `updated_at` AND the stored `ci_conclusion` is terminal-good (`success`/`skipped`). PRs recorded as pending or failing always get the per-PR fetch until CI concludes green: completing check runs do **not** bump a PR's `updatedAt`, so an unchanged `updatedAt` proves nothing while CI is in flight. A DONE verdict still requires the full Step 2 criteria — quiet only means "nothing changed since the state was written", so a PR that went quiet while NEEDS-FIX stays NEEDS-FIX.

On an all-quiet cycle the listing query is the only API call made — that's the point: under a long `/loop`, most cycles are all-quiet, and this collapses them to one call. Explicit-PR-list runs skip the listing but still read/write state. After each cycle (Step 6), write back every swept PR's `updated_at`, `head_sha`, `ci_conclusion`, and newest `last_comment_at`, and drop keys for PRs no longer open so merged/closed PRs don't accumulate. Treat a missing file as `{}`.

## The loop, one full iteration

Follow it exactly — the order matters because re-scheduling has to happen unconditionally at the end.

### Step 1: Sweep all PRs in parallel

Read the state file first and mark quiet PRs per **Sweep state** — they skip this step entirely. For each remaining PR, run these queries in parallel (one Bash call per PR is fine):

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

**Mergeability** — `gh pr view <#> --repo <owner/repo> --json mergeable -q .mergeable`. `CONFLICTING` means the base moved on and the PR no longer fast-forwards; route to **Resolving merge conflicts**.

**Review threads (inline)** — use the GraphQL API. The first comment's `author.login` is what you tag bot-vs-human against; its `databaseId` is what you POST replies to; the thread `id` (a `PRRT_kw...` token) is what you pass to `resolveReviewThread`:

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

Pipe through a small Python filter that keeps only `isResolved: false` entries and prints `thread_id | author | databaseId | bodyText[:200]`. Tag each surviving thread **bot** or **human** per the rules above.

**Reviews (latest verdict per reviewer)** — needed for the state axis (who approved, who blocked):

```bash
gh api "repos/<owner/repo>/pulls/<#>/reviews" \
  --jq '[.[] | {user: .user.login, type: .user.type, state, body, submitted_at}]
        | group_by(.user)
        | map(sort_by(.submitted_at) | last)'
```

A reviewer's **overall body** (the L3 source — e.g. one big "here's what to fix" comment) is the `body` on their latest `APPROVED`/`CHANGES_REQUESTED`/`COMMENTED` review.

**Issue-level comments** (top-level PR comments outside any review) — rarer but real:

```bash
gh api "repos/<owner/repo>/issues/<#>/comments" \
  --jq '[.[] | select(.user.type != "Bot") | {id, user: .user.login, body, created_at}]'
```

**Greptile summary comment (confidence score + T-Rex logs)** — Greptile's *first* post on a PR is a top-level **issue comment**, not a review body (its review body is empty), so it slips past *both* the reviews query and the bot-filtered issue-comment query above. Fetch it explicitly:

```bash
gh api "repos/<owner/repo>/issues/<#>/comments" \
  --jq '.[] | select(.user.login=="greptile-apps[bot]") | .body' | tail -1
```

It carries a **Confidence Score: N/5** and a collapsed **🦖 T-Rex Logs** section (runtime findings from Greptile actually executing the code). It's an **L3-bot** source — read it per **The Greptile summary comment** below.

### Step 2: Classify each PR (fill in the matrix)

For each PR, bucket every finding into a layer (L1 / L2 / L3) tagged with author + state per the matrix. Then assign the PR a disposition:

- **DONE** — CI green (latest-per-name) AND mergeable AND zero unresolved threads (bot or human) AND no unaddressed Greptile **summary-only** finding (see "The Greptile summary comment") AND every blocking human review has been turned around (re-requested) or all its findings filed as follow-ups.
- **WAITING** — checks include `in_progress/running` items (Cursor BugBot mid-review, e2e shards) but nothing failing, threads are clean, no new human verdicts. Not done; **don't dispatch** — the next iteration rechecks.
- **NEEDS FIX** — anything else: a failing check, a conflict, an unresolved thread, a summary-only Greptile finding, an unaddressed `CHANGES_REQUESTED`, or triaged approved-PR nits.

A NEEDS-FIX PR is **gated** (needs Step 3 confirmation) iff it has a live human **approval** AND this cycle would push at least one **avoidable** commit to it — anything that isn't merge-required. Avoidable = L2/L3 human non-blocking nits (the fix-here-vs-follow-up class) *and* any bot-thread or Greptile-summary code-fix on the approved PR (you could pushback-resolve or defer it, so spending the approval on it is a judgment call). **Autonomous** = merge-required fixes (a real CI failure, a conflict) when they're the *only* work on an approved PR, plus *all* findings on non-approved PRs (`CHANGES_REQUESTED`, `COMMENTED`, unreviewed).

**Gating is per-PR, not per-finding.** If a PR is gated, its *entire* fix waits for the confirm — including any autonomous sub-findings it also has (a flake rerun, a bot thread). They're all handled by the one agent dispatched after the gate, so the PR still pushes exactly once. (Non-push actions like a rerun or a pushback-resolve don't void approval, but they ride along with that single agent rather than firing separately — simpler than splitting a PR's work across the gate.)

The loop stops only when ALL PRs are DONE simultaneously.

### Step 3: Confirm gate (the risky class only)

If any PR is gated, surface **one batched triage** and wait for the user. Score each non-blocking human comment:

- **Strong "fix here"** — typo, doc nit, rename, missing JSDoc, dead import, single-line refactor, missing null-check on already-touched code, test-name fix. Cheap, in-scope, the reviewer expects it to land.
- **Borderline → lean fix-here** — 1–20 LOC behavioral change in a file the PR already touches, no new tests required.
- **Strong "follow-up"** — new feature surface, multi-file refactor, "while you're here, also do X" scope-creep, architectural change, anything past the ticket's acceptance criteria, or anything the reviewer themselves prefaced with "non-blocking, but…" / "in a follow-up".

```
APPROVED-PR triage — 8 non-blocking comments across PR #820, #822, #831

PR #820 (approved by @alice):
  [fix-here]  inline:   "rename `cfg` to `config` for consistency" → 1-line rename
  [fix-here]  overall:  "add a TODO comment explaining the cache TTL"
  [follow-up] inline:   "while you're here, refactor the auth layer to the new SDK"
PR #822 (approved by @bob):
  [fix-here]  inline:   "missing test for the empty-array case"
  [follow-up] overall:  "extract this into a shared util — 3 other places need it"
PR #831 (approved by @alice):
  [fix-here]  inline:   "typo: 'recieved' → 'received'"
  [follow-up] inline:   "add structured logging here in a follow-up"

Recommendation: 4 fix-here, 4 follow-up.
Heads up: any fix-here on #820 / #822 / #831 invalidates the approval and forces re-review.
Proceed? (yes / no / edit specific items)
```

Wait for confirmation before dispatching agents for gated PRs. If the user says "edit", let them flip individual items between fix-here and follow-up, then re-confirm. **Autonomous PRs do NOT wait** — dispatch them in parallel immediately (Step 4); only the gated PRs block on this answer.

If an approved PR has *only* a merge-required fix (no avoidable work), it isn't gated — fix and push it autonomously, and just note in the report that the approval was auto-invalidated (GitHub re-requests the approver). Don't ask permission to fix red CI; do ask before spending an approval on a deferrable nit.

### Step 4: Dispatch one fix agent per PR (in parallel)

For each NEEDS-FIX PR (gated ones after confirmation), dispatch exactly **one** fix agent (Agent tool, `general-purpose`). Give each agent:

- The exact worktree path
- The full bucketed finding set for its PR (L1 checks, L2 threads with `databaseId` + thread `id` + author + state, L3 review-body items, L3 Greptile summary-only findings, conflict state), plus the fix-here/follow-up decision for any gated items
- The follow-up tracker (`linear` or `jira`) and the origin ticket ID (from the branch name)
- The fix protocol below

**One agent per PR, one coordinated push.** PRs are independent (separate worktrees) so parallel is safe — but never dispatch two agents for the same PR, and never let a PR push twice in one cycle. Batching every layer into one push is what keeps approvals and CI/bot re-triggers from thrashing. ("One push" means one push of **commits**. The agent's other GitHub actions — flake reruns, thread replies + resolves, the `size/override` label-add and its rationale comment, follow-up tickets — are separate non-push API calls that don't invalidate approval and may fire independently of the push. The size-override label legitimately re-fires CI on the `labeled` event; that's expected, not thrash to avoid.)

### Step 5: Re-arm the loop — CRITICAL

**Before finishing your reply, call `ScheduleWakeup` for ~10 minutes (600 seconds) with the same loop prompt.** If you skip this, the loop dies silently — no error, just silence after the next 10 minutes pass.

This bites because it's easy to forget after dispatching fix agents (the active work feels like the "real" output). Treat the `ScheduleWakeup` call as the closing brace of the iteration — write it before you compose the report so muscle memory doesn't betray you.

The only time you DON'T reschedule is when **every** PR is DONE and you're reporting the final terminating state. Re-arming is unconditional otherwise — **including a cycle where you dispatched nothing** (e.g. every live PR was WAITING on in-progress checks). "No agents this cycle" is not "done"; only all-DONE is done.

### Step 6: Update state + report iteration

Write the sweep state back per **Sweep state** (every swept PR's current facts; prune closed/merged keys).

Then report, under 300 words: a status table per PR (include Greptile's confidence score N/5 when present; mark quiet PRs `quiet — skipped`) + what was fixed/filed this cycle + any **size-gate actions** + next wakeup ETA (or `DONE`).

### Step 7: On the next firing — recheck, re-request, or re-loop

When the wakeup fires, re-run Step 1 for the PRs that had fixes pushed last cycle. Then for each:

- **CI broken by our fix** → treat as a fresh L1 failure: investigate, fix, push, loop again.
- **New human comments since last fix** → fold into the next iteration's classify-and-dispatch.
- **New bot threads since last fix** → handle them **inline this cycle**. (This is one skill now; there is no `/pr-sweep` to punt to — you *are* it.) Don't be surprised by new threads on files you just fixed; the bot re-reviewed. Treat as fresh findings.
- **Clean** (CI green, conflict-free, all original threads resolved/filed) → run **Convergence** (re-request + summary comment) for any human who blocked.

A PR reaches **terminal state** when it's DONE per Step 2 — including that re-request has fired for any blocker (or all their findings were filed as follow-ups, needing no commit and no re-request).

---

## The fix protocol (one agent, all of its PR's feedback)

The agent receives the worktree path, the bucketed findings, the follow-up tracker, and these instructions. Make **all** commits for the PR, verify, then push **once**.

1. **`cd` into the worktree** and stay there. Auto-derive the path if not provided; `git worktree add <path> <branch>` if it doesn't exist.

2. **Pull latest**: `git pull --rebase`. If the LFS-pointer dance blocks it (Mondrio has stale LFS pointer files in `backend/tests/fixtures/surveys/*.json` that show as modified in every worktree), run:
   ```bash
   git update-index --assume-unchanged backend/tests/fixtures/surveys/*.json
   ```
   before pulling. Restore with `--no-assume-unchanged` at the end if you can; it's not critical. If the rebase hits conflicts, go to **Resolving merge conflicts**.

3. **Layer 1 — CI checks + size gate.** For each failing check, investigate via `gh run view <run-id> --log`:
   - **Size gate** (`PR Size Gate` / "Diff size (excl. generated)") → it's a *policy gate*, not a code bug; follow **Handling the size gate** and skip the rest of this bullet.
   - **Flake** (failures in tests unrelated to the PR's diff scope) → `gh run rerun <run-id> --failed`. Don't fix code for flakes. Confirm the hypothesis by correlating failing test files against `git diff --name-only` — no overlap ⇒ almost certainly a flake.
   - **Real failure** → fix the underlying code, add a regression test if you can.
   - **Title / Conventional Commits** (`action-semantic-pull-request`) → if the issue is the PR title (e.g. uppercase after the colon, or it starts with a ticket ID/acronym like `MON-1096`/`PR-review`), `gh pr edit <#> --title "..."`. Title edits auto-re-fire the check; no code commit.

4. **Layer 2 — inline review threads (bot + human, identical mechanics).** For each unresolved thread:
   - Read the body carefully. Apply the **smallest correct fix**. One commit per finding, Conventional Commits (`<type>(<scope>): <description> (MON-XXX)`), ticket from the branch name.
   - Reply with the fix SHA, then resolve:
     ```bash
     gh api -X POST "repos/<owner/repo>/pulls/<#>/comments/<databaseId>/replies" \
       -f body="Fixed in <SHA>. <one-line explanation>"
     gh api graphql -f query='mutation{
       resolveReviewThread(input: {threadId: "<thread-id>"}) { thread { isResolved } }
     }'
     ```
   - **Per-thread nuances** (these are the only places author/state changes the action):
     - **Bot thread** → fix, or push back per **Pushback-worthy findings** (then still resolve).
     - **Human thread, blocking** (PR `CHANGES_REQUESTED`) → fix. Higher bar to push back than for bots.
     - **Human thread, non-blocking** (PR `APPROVED`/`COMMENTED`) → already triaged in Step 3. If **fix-here**, fix + reply + resolve as above. If **follow-up**, do **not** change code; file a ticket (see below) and reply `Filed as follow-up: <ticket-url>`, then resolve.

5. **Layer 3 — top-level findings (review bodies + Greptile summary):**
   - **Greptile summary-only finding** (from the confidence-score reasoning or T-Rex logs, with no matching inline thread) → treat as a bot finding: smallest correct fix, one commit, **no reply** (the summary isn't threadable). If it duplicates an inline thread you're already fixing in Layer 2, skip it — one commit covers both. Push back per **Pushback-worthy findings** if it's wrong or out of scope (no reply; note it in the report).
   - **`CHANGES_REQUESTED` body** → split the requested changes into discrete fixes, **one commit per requested change** so the reviewer can scan commit-by-commit. **No reply to the review body** — the Convergence re-request is the response.
   - **`APPROVED`/`COMMENTED` body** → already triaged in Step 3. Fix-here items become commits (no thread reply needed for a top-level approval comment). Follow-up items become tickets, acknowledged with **one** PR-level comment: `gh pr comment <#> --body "Filed as follow-up: <ticket-url> (re: @reviewer's note about …)"`.

6. **Follow-up tickets** (for every follow-up decision): do **not** modify the PR.
   - **Linear** (default) — `mcp__claude_ai_Linear__save_issue`. Title `Follow-up: <short summary>`. Body: quote the reviewer's comment verbatim, link the PR, name the origin ticket. Use the origin ticket's team if derivable from the branch; else the agent's default team.
   - **Jira** — the project's standard Jira CLI/MCP path; same title/body shape.

7. **Verify before pushing**: `tsc --noEmit` (frontend) or `uv run pyright && uv run ruff check .` (backend). Don't push code that breaks type-check or lint.

8. **Push once**: plain `git push` (no force unless a rebase landed cleanly — then `--force-with-lease`, never `--force`).

### Handling the size gate (Mondrio platform)

`mondrio-platform` runs a **PR Size Gate** (`.github/workflows/pr-size.yml`, check name *"Diff size (excl. generated)"*) that **fails** any PR whose *effective* diff exceeds **1000 LOC** (the aim is ~400). Effective diff = `additions + deletions`, **excluding** lockfiles, `backend/supabase/migrations/`, `frontend/src/components/ui/`, `frontend/src/integrations/supabase/types.ts`, and the ADR dirs — **tests are NOT excluded.** A `size/override` label bypasses the cap; the workflow re-runs on `labeled`, so adding the label flips the check green. Per the repo's CLAUDE.md the override is "**for the exception, not the rule — default to splitting**," and it **requires a comment explaining why the PR can't be split** (a human reviewer reads that comment).

So this check is **never a code fix**:

1. **Guard — don't double-act.** `gh pr view <#> --repo <owner/repo> --json labels`. If `size/override` is present, do nothing — the gate passes next run. Never add the label twice or post a second override comment.

2. **Get the effective LOC** (authoritative — mirrors `pr-size.yml`; if that workflow's exclusion list changes, update this regex):
   ```bash
   EXCLUDE='(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock)$|^backend/supabase/migrations/|^frontend/src/components/ui/|^frontend/src/integrations/supabase/types\.ts$|^docs/adr/|^docs/explanation/architecture/adr/'
   gh api --paginate "repos/<owner/repo>/pulls/<#>/files?per_page=100" \
     | jq --arg ex "$EXCLUDE" '[ .[] | select(.filename | test($ex) | not) | (.additions + .deletions) ] | add // 0'
   ```

3. **Decide: override, or recommend a split?** Read `git diff --stat origin/develop...HEAD` alongside the PR title/ticket:
   - **Cohesive single change** — one feature/fix whose files move together, where splitting would only yield non-functional, non-independently-mergeable intermediate PRs → **override** (step 4).
   - **Clearly separable, OR way over the cap** — decomposes into independently-landable changes (unrelated scopes, or a standalone refactor bundled with a feature), **or** effective diff **> ~2000 LOC** (>2× cap) → **do NOT override.** STOP and report a **split recommendation** naming the natural seams (by scope / ticket / feature). This is the repo's default; override is the exception.

4. **Override (cohesive case only).**
   - `gh pr edit <#> --repo <owner/repo> --add-label "size/override"`
   - Post **one** comment with a **specific, honest** rationale — never boilerplate. State what the PR does, why the files are one cohesive change, why splitting would create non-functional intermediate PRs, and the effective LOC. If you can't state an honest reason it's unsplittable, you're in the split case — go back to step 3.
     ```bash
     gh pr comment <#> --repo <owner/repo> --body "**size/override rationale:** <specific reason this change is cohesive and can't be split into independently-mergeable PRs>. Effective diff ~<N> LOC (excludes lockfiles, migrations, generated UI/types, ADRs; aim ~400, hard cap 1000)."
     ```

5. **Report it** every iteration + in the DONE report (PR#, effective LOC, one-line rationale), and surface every split recommendation. Don't bury either.

## Resolving merge conflicts during the loop

Conflicts surface in two places: at `git pull --rebase` in a worktree (the remote branch picked up commits the loop didn't make), or as a `Mergeability: CONFLICTING` state when the base branch (typically `develop`) moved on. Both are resolvable in the loop. The agent must investigate before resolving; "take ours" / "take theirs" without understanding which side is right is how PRs land regressions.

### Investigation order

1. `git status` — confirm what's conflicting.
2. `git diff` on each conflicting file — read both sides of the `<<<<<<<` / `=======` markers.
3. `git log --oneline <conflicting-commit-range>` — see what each side did and why.
4. For each conflicted hunk, decide:
   - **Take ours (the branch's version)** — the branch's change is the substantive feature work and the upstream change is a refactor the branch can absorb.
   - **Take theirs (the upstream version)** — upstream already did the work the branch was trying to do (common when a parallel PR landed first). Often the branch's commit becomes **empty** — that's OK, drop it (`git rebase --skip` / `--allow-empty=drop`).
   - **Manual merge** — both sides changed the same area for different reasons and both need to land. Combine by hand.
5. After resolving each file: `git add <file>`, then `git rebase --continue`.

### Concrete patterns from real runs

- **Empty commit after upstream did the same work**: the branch's commit was "unify `TierConfig` import," but upstream landed that exact change first. Take upstream's version; the commit drops as empty during rebase; the branch ends up 1 commit shorter — a *good* outcome, the work was duplicated.
- **Cherry-pick conflict on a format-only commit**: when splitting into stacked PRs, a `style:` commit may want to format files not yet on the new branch. `git rm` the missing files from the cherry-pick — they get re-added cleanly by a later commit in the stack.
- **Mid-loop push from user**: pull --rebase shows 6 unknown commits. Don't clobber them with `--force-with-lease` — rebase the loop's fix commits ON TOP. The user's intent was to expand the branch, not to be overwritten.

### When to STOP instead of resolve

- The conflict is in a file the agent doesn't understand the architecture of, AND `git log` of both sides shows substantive logic from each.
- The conflict involves removing code the user explicitly added since the loop started.
- More than ~3 conflicting files OR more than ~50 LOC of conflict to resolve manually — the branches have drifted too far for a routine sweep.

STOP means: report the conflict in detail (files, both sides of the diff, both sides' commit messages) and let the user decide.

### After conflict resolution

- Plain `git push` if the rebase was clean and the upstream is the same branch you pulled from.
- If the rebase rewrote shared commits, `--force-with-lease`, **NEVER** plain `--force`. `--force-with-lease` aborts if someone pushed between your last fetch and now — that safety check has saved real work.
- Don't comment on threads about the rebase unless a thread specifically asks. The loop closes threads; it doesn't narrate housekeeping.

## Pushback-worthy findings (bots and humans)

Not every suggestion is worth implementing. Defer with a thoughtful reply (then resolve the thread) when:

**Bots** (Greptile / Cursor) — lower bar to push back:
- The suggested refactor would add a 4th copy of logic that already exists in 2-3 utility modules. Don't add the 4th — and because this is *real deferred work*, file a follow-up ticket for the unification and link it in the resolving reply. (A pushback that merely *declines* — "not our convention", citing a precedent file — needs no ticket, just the reply.)
- The suggested rule isn't actually a team convention (e.g. "store mocks in a dedicated `mocks/` dir" when the team co-locates helpers in test files). Cite an existing file as precedent.
- The change would expand PR scope past the ticket's acceptance criteria. Defer with "out of scope, filed as follow-up."

**Humans** — usually more right than bots, so the bar is higher. Push back only when:
- The suggestion contradicts an explicit pattern in the repo's CLAUDE.md or the ticket's `prep-ticket` notes — cite the line.
- The suggestion would expand the PR past acceptance criteria — defer with `Filed as follow-up: <ticket-url>` and resolve.
- The suggestion is technically incorrect (would break a tested invariant) — cite the failing test or invariant. Resolve only if confident.

Pushback only works when the reply is **specific** (cites a precedent file, names a follow-up ticket, points at a test) and the agent has actually looked at the code. A weak defer ("we don't do that here") will get reopened. When in doubt on a human comment, **don't push back** — file as follow-up and let the user adjudicate.

## Convergence: re-request review + summary comment

When a PR that had a blocking human review goes clean (CI green, conflict-free, all threads resolved/filed), re-request review and post one handoff comment. **Do this only on a later firing, never in the same cycle you pushed the fixes** — wait for CI to re-confirm green on the new commits first. Re-requesting before CI validates risks sending the reviewer back to a red PR.

```bash
gh api -X POST "repos/<owner/repo>/pulls/<#>/requested_reviewers" \
  -f reviewers='["<login>", ...]'
```
for each human reviewer whose latest verdict was `CHANGES_REQUESTED`. (Don't re-request from approvers — GitHub auto-re-requests them when a fix-here commit invalidated their approval. The POST silently no-ops if the reviewer is already requested, so it's safe to call defensively.)

Then post one PR-level summary so the reviewer isn't hunting through commits:
```bash
gh pr comment <#> --body "$(cat <<'EOF'
Re-requesting review — addressed feedback in:

- <sha1> <commit subject>
- <sha2> <commit subject>

Filed as follow-up:
- <ticket-url> <follow-up summary>
EOF
)"
```

## Constraints — non-negotiable

- **Never bypass hooks** with `--no-verify`. If a hook fails, the fix the hook flagged is the real fix.
- **Never push to `develop`, `main`, or any base branch.** Feature branches only.
- **Never force-push** (`--force`, `--force-with-lease`) unless a rebase landed cleanly and the upstream is the same branch. Default to plain `git push`; if you must force, `--force-with-lease` only.
- **Don't push avoidable work to an `APPROVED` PR without the Step 3 confirm gate.** Any commit that isn't merge-required — a nit, a bot suggestion, a bot bug-fix — waits for confirmation, because it spends the approval on something deferrable. A merge-required fix (real CI failure, conflict) may push without asking *only when it's the only work on that PR* (surface it in the report). If the PR also has avoidable work, the whole PR is gated and everything batches into one post-confirm push — never push an approved PR twice in a cycle.
- **Never dismiss a reviewer's review.** Even if you think they're wrong, surface to the user; don't programmatically dismiss.
- **STOP instead of patching** if a finding requires:
  - More than ~100 LOC of code change
  - An architectural decision ("should this hook be split?")
  - A product call ("should this UX behave this way?")
  - Touching code outside the PR's existing diff scope by more than a small adjacent fix

  STOP means: report the finding's details and recommended path back to the loop. The user decides next. A **blocking reviewer's** explicit request is in-scope by definition (they're the merge gate) — but if satisfying it would trip one of the criteria above (e.g. the requested test needs a >100-LOC harness, or an architectural change), STOP and surface rather than half-implementing it.

## Edge cases worth knowing about

- **Approval-then-changes_requested by the same reviewer**: GitHub keeps the latest verdict. If @alice approved on commit A then requested changes on B, treat the PR as `CHANGES_REQUESTED` — don't fold the earlier approval into the triage batch.
- **Multiple reviewers in different states**: e.g. @alice approved + @bob requested changes. Handle bob's findings under the blocking protocol; handle alice's nits (if any) under the triage protocol. Re-request from @bob when done — not @alice.
- **Stacked PRs**: PR B's base is PR A's branch (not `develop`). After A merges, B needs `gh pr edit <B> --base develop`. The sweep handles stacked PRs fine; flag the retarget in the final report.
- **Reviewer asked for a follow-up explicitly** ("let's do this in a follow-up"): treat as follow-up regardless of size — the reviewer told you the answer.
- **Reviewer asked you NOT to file** ("just a thought, don't bother filing"): skip both fix and ticket; reply "Noted, thanks" and resolve.
- **Bots replying to their own resolved threads**: treat as a new finding only if the follow-up asks for additional code change.
- **Cursor BugBot still `in_progress`**: if all threads are clean but Cursor is mid-review, don't declare DONE — wait one more cycle (WAITING).
- **Reviewer comments on a PR you already retitled**: title edits re-fire the conventional-commits check but do NOT dismiss reviews — reviews persist.
- **Greptile re-reviews after a push**: it updates its summary comment with a new confidence score and fresh T-Rex logs (the "Re-trigger Greptile" / re-review path). Re-read Greptile's latest summary each cycle — the score and findings move as you push fixes; a rising score signals the fixes landed.

## Final DONE report

When every PR is in terminal state:

1. Don't reschedule.
2. Per-PR final table: PR#, commits added during the loop, threads resolved/replied (bot + human), follow-up tickets filed (with links), re-request status, any deferrals.
3. Call out: stacked-PR retargets needed; any STOPs needing user adjudication.
4. List the follow-up tickets created and any bot/human pushback deferrals — these are the most valuable byproduct, capturing tech debt and reviewer wisdom the bots/humans noticed but the PR couldn't absorb.
5. List any **size-gate actions**: PRs where `size/override` was applied (effective LOC + rationale) and any PRs recommended for splitting instead.

## Iteration cadence — why 10 minutes

The number isn't arbitrary:
- Greptile and Cursor BugBot post the first round 5–12 minutes after Ready-flip. A 5-minute cadence misses the bot's first pass; 30 minutes wastes wall-clock. Humans re-review on their own schedule, which 10 minutes also absorbs.
- The Anthropic prompt cache has a 5-minute TTL. Below 5 minutes the conversation context stays cached (cheap); above it, the next iteration pays a cache miss anyway, so amortize it — 10 minutes is past the miss and lets bots/CI do meaningful work.
- CI runs (e2e shards in particular) take 5–7 minutes. A 10-minute gap typically catches one full run cycle.

Adjust to taste for faster/slower projects, but don't go below 5 minutes (cache thrash) or above 20 (loop loses its rhythm).
