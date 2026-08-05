# Collection, Current State, and Classification

Read this file in full before collecting or classifying non-quiet PRs. GitHub fields, bot identities, and Greptile shape are provider-sensitive: validate them against the current repository/provider when a command or field has changed.

## Scope and state

Default scope:

```bash
gh pr list --author @me --state open --json number,title,headRefName,baseRefName,isDraft,url,updatedAt
```

Exclude drafts. An explicit PR list is exact scope and skips listing. Confirm once if the default produces roughly more than eight PRs or unrelated repositories.

Read `~/.local/state/pr-sweep/state.json` before per-PR calls. Treat a missing file as `{}` and key entries by PR URL:

```json
{
  "https://github.com/owner/repo/pull/820": {
    "updated_at": "2026-07-12T17:05:00Z",
    "head_sha": "abc123",
    "ci_conclusion": "success",
    "last_comment_at": "2026-07-12T17:00:00Z"
  }
}
```

A PR is quiet only when listing `updatedAt` equals stored `updated_at` and stored CI is terminal-good (`success` or `skipped`). Skip its per-PR calls but retain its previous disposition. Pending/failing CI is never quiet based on metadata alone because check completion does not bump `updatedAt`. Explicit-list runs still use state. After every cycle, persist current facts for every swept PR and prune keys no longer open.

## Parallel collection per non-quiet PR

Collect these sources concurrently for each PR. Do not let one provider failure erase the other evidence.

### CI: latest run per check name

Use the head SHA and checks API. The load-bearing algorithm is **latest run per check name**, not every historical run:

```bash
sha=$(gh pr view <#> --repo <owner/repo> --json headRefOid -q .headRefOid)
gh api "repos/<owner/repo>/commits/$sha/check-runs?per_page=100" --jq '.check_runs
  | group_by(.name)
  | map(sort_by(.started_at) | last)
  | .[]
  | select(.conclusion != "success" and .conclusion != "neutral" and .conclusion != "skipped")
  | "\(.status)/\(.conclusion // "running") — \(.name)"'
```

`success`, `neutral`, and `skipped` are non-failing. `in_progress`, `queued`, or running means `WAITING` when everything else is clean. Ignore an older failure when that check name's newest run is green.

### Mergeability

```bash
gh pr view <#> --repo <owner/repo> --json mergeable -q .mergeable
```

`CONFLICTING` routes to conflict investigation; do not give a generic fixer authority to choose a side first.

### Unresolved inline threads

```bash
gh api graphql -f query='query{
  repository(owner:"<owner>", name:"<repo>") {
    pullRequest(number: <#>) {
      reviewThreads(first: 50) {
        nodes { id isResolved comments(first: 100) {
          nodes { author { login } bodyText databaseId createdAt }
        } }
      }
    }
  }
}'
```

Keep unresolved threads and preserve two identifiers with distinct purposes:

- the opening comment **`databaseId`** (`C-*` in simulations) is the reply target;
- the **review thread ID** (`T-*` / `PRRT_*`) is the resolution target.

Do not swap them. Inspect all comments: a human reply inside an automated thread makes the active thread human.

### Reviews: latest verdict per reviewer

```bash
gh api "repos/<owner/repo>/pulls/<#>/reviews" \
  --jq '[.[] | {user: .user.login, type: .user.type, state, body, submitted_at}]
        | group_by(.user)
        | map(sort_by(.submitted_at) | last)'
```

The **latest verdict per reviewer** wins. An older `APPROVED` followed by `CHANGES_REQUESTED` is blocking, not approved. The latest review body is its L3 content.

### Issue comments and latest Greptile summary

Collect current human issue-level comments and Greptile separately:

```bash
gh api "repos/<owner/repo>/issues/<#>/comments" \
  --jq '[.[] | select(.user.type != "Bot") | {id, user: .user.login, body, created_at}]'

gh api "repos/<owner/repo>/issues/<#>/comments" \
  --jq '.[] | select(.user.login=="greptile-apps[bot]") | .body' | tail -1
```

Re-read the latest Greptile summary after every push; its score and T-Rex observations can change.

## Bot/human classification

Treat a reviewer as bot when `user.type == Bot`, login matches the current known-bot list, or the opening body carries the `🤖 Automated comment by` header. Current common logins include `greptile-apps[bot]`, `cursor[bot]`, `cursoragent[bot]`, `dependabot[bot]`, `copilot[bot]`, `github-actions[bot]`, `coderabbitai[bot]`, `renovate[bot]`, and `sonarqubecloud[bot]`. Validate this time-sensitive list rather than assuming it is complete.

A human reply in the thread makes it human. Ambiguity defaults to human.

## Form × state matrix

| Form | Current condition | Action class | Reply form | Approval risk |
|---|---|---|---|---|
| L1 real CI | failing | code fix + feasible regression test | none | merge-required |
| L1 flake | unrelated to diff | rerun failed job | none | no commit |
| L1 title | title-only convention failure | edit title | none | no commit |
| L1 size | policy check | existing override wait, cohesive override, or split STOP | one rationale only for new override | policy action |
| L1 conflict | `CONFLICTING`/rebase conflict | investigate, resolve safely, or STOP | none | merge-required if safe |
| L2 bot | unresolved | smallest fix or evidenced pushback | reply via comment `databaseId`; resolve review thread ID | avoidable on approved PR |
| L2 human blocking | latest verdict `CHANGES_REQUESTED` | fix or high-bar evidenced pushback | reply + resolve | autonomous on non-approved PR |
| L2 human nonblocking | `APPROVED`/`COMMENTED` | approved triage: fix-here/follow-up/no-file | reply + resolve | avoidable |
| L3 Greptile | latest summary | summary-only fix/pushback; de-duplicate L2 | **never reply** or resolve summary | avoidable on approved PR |
| L3 human blocking | `CHANGES_REQUESTED` body | discrete commits | no direct reply | autonomous on non-approved PR |
| L3 human nonblocking | `APPROVED`/`COMMENTED` body | approved triage | no reply for fix; one PR-level follow-up acknowledgment | avoidable |

## Greptile de-duplication and accounting

The summary contains context, a confidence score, and possibly T-Rex runtime observations. Confidence is a triage signal, never an independent merge gate.

Build a stable finding ledger before dispatch:

1. Match each summary concern to any L2 inline thread by file, behavior, and failure mode.
2. If matched, assign one finding key to the inline thread and record the summary as corroborating evidence. Fix it once.
3. If unmatched, assign a stable summary-only key. It may receive one commit or one evidenced pushback, but **never reply** to or resolve the summary.
4. Carry finding keys and commit SHAs across cycles so updated summary wording does not create a duplicate fix.

Before dispatch, reconcile **every collected finding** to **exactly one terminal action** in the cycle ledger: fix/commit, rerun, reply-resolve, follow-up, evidenced pushback, explicit wait, or STOP. A duplicate summary maps to its inline key; each genuine summary-only item keeps its own assigned action. Do not dispatch with an unassigned finding, and report the ledger's finding-to-commit/pushback accounting.

Report the current score, but judge completion by underlying findings.

## Disposition decision

- **DONE:** newest-per-name CI is green; mergeable; zero unresolved inline threads; no open summary-only finding; every latest blocking human verdict has been turned around/re-requested or all its findings were filed as follow-ups. A size override already present is not instantly DONE: wait/recheck the labeled-event check until its latest run is terminal-good.
- **WAITING:** current feedback is clean and the only incomplete state is live CI/bot/review processing, including a pending size-override rerun. Dispatch nothing and re-arm.
- **NEEDS FIX:** any failure, conflict, unresolved thread, summary-only finding, unaddressed blocking review, approved triage, or STOP/user decision remains.

Only all selected PRs simultaneously `DONE` terminates the sweep.
