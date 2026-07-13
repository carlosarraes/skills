---
name: qa-pr
description: >
  Use when the user wants to QA a PR and leave observable evidence ON the PR for
  reviewers — "qa-pr", "qa this PR and post the results", "prove this PR works on
  the PR", "attach test evidence to #123". The outward-facing sibling of qa-ticket:
  qa-ticket QAs your own branch privately; qa-pr runs the same acceptance testing
  against a PR and posts one sticky evidence comment with screenshots/GIFs so a
  human reviewer can observe behavior instead of re-reasoning about the diff.
  Takes a PR number/URL. Localhost only; checkpoints before posting.
---

# QA PR: post observable evidence on a PR

Reviewers trust behavior they can see over reasoning they have to check. `qa-pr`
runs acceptance testing against a PR's branch and posts one evidence comment —
per-case pass/fail plus screenshots and GIFs — so the reviewer observes the feature
working instead of reconstructing it from the diff. It's `qa-ticket` pointed at
someone else's PR (or your own) with an outward evidence artifact.

**Relationship to qa-ticket:** the test-planning and execution engine is
`qa-ticket`'s — this skill does **not** re-derive it. qa-pr adds three things:
checkout of the PR branch, media capture, and the sticky PR comment. Everything
about *what to test and how* (test-plan generation from the ticket+diff, happy /
edge / error cases, backend via curl, frontend via agent-browser, localhost-only,
fix-and-retry) comes from `qa-ticket` — invoke it, don't duplicate it.

## Bot identifier — REQUIRED on the posted comment

The evidence comment must begin with:

```markdown
> [!NOTE]
> 🤖 Automated comment by **QA PR** — not written by a human
```

This is what marks it automated so a reviewer (and `pr-sweep`) can tell it from a
human comment.

## Workflow

### Step 1: Resolve and check out the PR

```bash
gh pr view <#> --json number,headRefName,baseRefName,url,headRefOid,title
```

Check out the PR branch into a worktree (auto-derive the path per the project
convention, or `git worktree add <path> <branch>`; `gh pr checkout <#>` if simpler).
Derive the ticket ID from the branch name for context.

### Step 2: Plan + run the QA (via qa-ticket)

Invoke `qa-ticket` against the checked-out branch to generate the targeted test
plan and run backend (curl) + frontend (agent-browser) cases against localhost.
qa-ticket already fixes bugs it finds and retries; let it. Collect its per-case
pass/fail results.

> The user's dev environment must be running locally. If localhost isn't up, stop
> and ask — qa-pr never tests against staging/prod (qa-ticket's rule).

### Step 3: Capture observable evidence

For each meaningful case, capture media as it runs:

- **Frontend** — agent-browser screenshots at each key step. For a flow, capture a
  sequence of frames and assemble a GIF (`ffmpeg` from the frames, or reuse
  `demo-video`'s recording pieces if a moving capture is warranted).
- **Backend** — the actual request and response (curl command + JSON body), fenced
  in the comment; a screenshot only if there's a UI side effect.

Store media under the worktree's scratch dir; upload by attaching to the comment
(drag-drop isn't available headless — use `gh` to attach, or host the image inline
as a link the PR can render).

### Step 4: Checkpoint before posting

Posting to a PR is outward-facing. Show the user the assembled evidence comment
(verdict + per-case results + media list) and get a go-ahead before the first post.
On re-runs of a PR that already carries the evidence marker, update without asking.

### Step 5: Post one sticky evidence comment, upserted

Find any comment containing `<!-- qa-pr-evidence -->`; PATCH it if present, else
`gh pr comment`. Never post a second evidence comment — the latest run is on top,
prior runs collapse into a `<details>` block.

```markdown
<!-- qa-pr-evidence -->
> [!NOTE]
> 🤖 Automated comment by **QA PR** — not written by a human

## QA evidence — <verdict emoji> <PASS | PASS WITH NOTES | FAIL> <sub>(@ <short_sha>)</sub>

| Case | Type | Result | Evidence |
| --- | --- | --- | --- |
| <happy path> | frontend | ✅ | <screenshot/GIF> |
| <edge case>  | backend  | ✅ | <curl + response> |
| <error case> | backend  | ⚠️ | <note> |

<any bugs found + fixed this run, with SHAs>

<details><summary>Previous runs</summary>
<one line per prior run: `@ <sha> — <verdict>`>
</details>
```

### Step 6: Report

Terminal summary: verdict, per-case results, media captured, any bugs fixed during
QA (with SHAs), and the comment URL.

## Platform notes

- **GitHub:** full flow above (`gh` for checkout + comment upsert + media).
- **Bitbucket (zapsign/api):** `bt pr comment <id>` posts the evidence comment
  (top-level comments work); media is attached as links. Same bot header, same
  sticky-marker upsert via `bt pr comments` to find the prior one.

## Constraints

- Localhost only — never test against staging/prod (inherited from qa-ticket).
- Checkpoint before the first post (outward action).
- One sticky evidence comment per PR — upsert, never duplicate.
- Don't re-implement qa-ticket's test planning or execution — invoke it.
- On your own PR the evidence is still useful; on a teammate's PR, only post if the
  user asked you to QA it (don't surprise-comment on others' PRs).
