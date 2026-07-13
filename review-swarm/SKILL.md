---
name: review-swarm
description: >
  Use when the user wants a full multi-perspective review of a PR or branch —
  "review-swarm", "swarm review", "swarm this PR", "full review on #123",
  "review before I flip it to Ready", or when they want independent reviewer
  agents' findings posted to a PR as inline comments. Accepts an optional PR
  number/URL or base branch as argument. Complements pr-sweep: review-swarm
  generates the review; pr-sweep drives the resulting threads to resolution.
---

# Review Swarm: Multi-Perspective PR Review

Runs independent review perspectives in parallel and posts findings as inline PR
comments plus one sticky summary. Each reviewer operates independently — none knows
about the others. Convergent findings (2+ reviewers, independently) carry higher
confidence.

Run it **before** flipping a PR to Ready (or before requesting human review): the swarm
catches what it can, `pr-sweep` then treats the posted threads as bot findings and
drives them to resolution — the whole point is that a human reviews less code.

## Bot identifier — REQUIRED on every posted comment

Every comment this skill posts to GitHub (inline review comments, review body,
top-level comments — **every single one**) must begin with:

```markdown
> [!NOTE]
> 🤖 Automated comment by **Review Swarm** — not written by a human
```

Never skip this header: it is what lets a reader tell agent output from author speech,
and it is the marker `pr-sweep` keys on to classify these threads as bot-authored.
On public repositories, never put absolute internal metrics (event counts, revenue,
user numbers) in a finding — use ratios.

## Workflow

### Step 1: Detect PR & gather diff

If `$ARGUMENTS` looks like a PR number or URL, use it. Otherwise detect the current PR:

```bash
gh pr view --json number,headRefName,baseRefName,url,headRefOid
```

If no PR exists, fall back to diffing against the base branch (`develop` if it exists
on the remote, else `main`, else `master`; `$ARGUMENTS` may name one). In that case
skip all PR posting and output the report to the terminal only.

Gather once, pass to every reviewer:

```bash
git diff <base>...HEAD --name-only
git diff <base>...HEAD
git log <base>...HEAD --oneline
git rev-parse HEAD
```

Store: PR number, owner/repo, base branch, changed files, full diff, commit log, HEAD SHA.

### Step 2: Launch the reviewers in parallel

Launch ALL reviewer agents in a **single message** with multiple Agent tool calls,
each **synchronous and unnamed** (`run_in_background: false`, no `name`) so every
reviewer's findings return directly as its tool result — a named/background reviewer
detaches and leaves the swarm waiting on findings that never arrive.
Each agent is told it is the sole reviewer. Never mention the other reviewers, their
count, or that a convergence analysis will happen — independence is what makes
convergence meaningful.

Pin each reviewer's model and effort explicitly (never inherit silently — see the
model & effort scorecard in `orchestrate/SKILL.md`):

| Reviewer | Source | Model / effort | Findings tag |
|---|---|---|---|
| qa-team | `qa-team` skill (this repo) | session model, high | `qa-team/<specialist>` |
| security | built-in `security-review` skill | session model, high | `security/<category>` |
| generalist | `feature-dev:code-reviewer` agent type | medium | `generalist` |
| carraes | `carraes-reviewer` skill | medium | `carraes` |

Dispatch each skill-backed reviewer per the skill-in-agent rule (never paraphrase the
skill into the prompt):

> Invoke the Skill tool: skill=`qa-team`. Follow the skill fully. The diff is already
> gathered — skip its Step 1 and use the material below. Do not write QAREPORT.md;
> return your findings in the STRUCTURED_FINDINGS format below as your final message.

**qa-team** — pass the diff material; tell it to return findings tagged
`qa-team/<specialist>` (e.g. `qa-team/security`, `qa-team/database`).

**security** — run the built-in `security-review` skill inside the agent with these
overrides stated in the prompt: the diff is supplied (do not re-derive the branch);
do not ask clarifying questions — state assumptions inline in the finding; do not
offer to fix anything; end immediately after the structured findings. Tag findings
`security/<lowercased-hyphenated-category>` (e.g. `security/idor`, `security/ssrf`).

**generalist** — a `feature-dev:code-reviewer` agent on the raw diff: bugs, logic
errors, convention violations, high-confidence issues only. Tag `generalist`.

**carraes** — only if `carraes-reviewer` is installed (check for its skill/dir);
skip silently otherwise. Reviews in the user's own voice and priorities. Tag `carraes`.

#### Reviewer output format

Every agent must end its response with exactly:

```
STRUCTURED_FINDINGS:
- file: <path> | line: <number or "general"> | severity: <CRITICAL|HIGH|MEDIUM|LOW|NIT> | reviewer: <tag> | body: <the review comment text>
...

OVERALL_SUMMARY:
<1 paragraph assessment>
```

No findings → `STRUCTURED_FINDINGS:` followed by `(none)`, then the summary.

### Step 3: Synthesize

**Deduplicate:** findings on the same file within ~5 lines, or clearly the same
concern, merge into one — note the convergence (`convergent: qa-team/database +
generalist`); convergent findings carry higher confidence.

**Score** (any CRITICAL → CRITICAL; 2+ HIGH or 1 HIGH + 2 MEDIUM → HIGH; 1 HIGH or
3+ MEDIUM → MEDIUM; else LOW) and map to a verdict:

- ✅ **APPROVE** — LOW, no actionable findings
- 💬 **APPROVE WITH NITS** — MEDIUM, minor suggestions
- ⚠️ **REQUEST CHANGES** — HIGH, fixes needed before merge
- 🚫 **BLOCKED** — CRITICAL, blocking issues

### Step 4: Post to PR

No PR detected → print the full report to the terminal and stop (offer to post if
the user supplies a PR). Posting is an outward action: on the **first** run against a
given PR, show the user the findings and get a go-ahead before posting; on re-runs
of a PR that already carries the summary marker, post without asking.

**4a — inline comments**, all findings with a file+line, as ONE review:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/reviews --method POST \
  -f event="COMMENT" -f commit_id="{HEAD_SHA}" \
  -f body="Review Swarm complete. See inline comments." \
  -f 'comments[]={path: "<file>", line: <line>, body: "<body>"}'
```

Each inline body: the bot header, then `**[<reviewer_tag>]** <severity emoji>
<severity>` (🔴 CRITICAL 🟠 HIGH 🟡 MEDIUM 🟢 LOW ⚪ NIT), then the finding text.
Convergent findings use `**[convergent: <tag1> + <tag2>]**`.

**4b — sticky summary, one per PR, upserted.** Find an existing comment containing
`<!-- review-swarm-summary -->`; PATCH it if found, `gh pr comment` otherwise. Never
post a second summary — the latest verdict sits on top, prior rounds collapse to one
line each inside a `<details>` block:

```markdown
<!-- review-swarm-summary -->
> [!NOTE]
> 🤖 Automated comment by **Review Swarm** — not written by a human

## Verdict: <emoji> <VERDICT> <sub>(round <N> @ <short_sha>)</sub>

<1-2 sentences>

### Key findings
<top findings, grouped by severity — current round only>

### Convergence
<findings flagged independently by 2+ reviewers, or "none">

### Reviewer summaries
| Reviewer | Assessment |
| --- | --- |
| 🔍 qa-team | <1 sentence> |
| 🛡 security | <1 sentence> |
| 🧑‍💻 generalist | <1 sentence> |
| 👤 carraes | <1 sentence, if run> |

<details><summary>Previous rounds (<n>)</summary>
<one line per prior round: `round <N> @ <sha> — <verdict>: <1-line disposition>`>
</details>
```

### Step 5: Report

Terminal summary: verdict, finding counts by severity, convergent findings, link to
the PR review, and the reminder that `pr-sweep` will pick the threads up (it
classifies header-marked comments as bot findings).

## Graceful degradation

- A reviewer's skill/agent type unavailable → warn (`<name>: skip`) and run the rest.
- Only one reviewer available → still run it; better than nothing.
- No PR → full report to terminal only.
- Review API awkward with many comments → fall back to individual
  `pulls/{pr}/comments` POSTs (same body format, same `commit_id`).

## Constraints

- Never post without the bot header.
- Never approve/request-changes via review event — always `COMMENT`; verdicts live in
  the summary text. (Stamping is `stamp-check`'s job, and it has its own gates.)
- Never run the swarm twice concurrently on the same PR.
- GitHub only for posting (v1). On Bitbucket repos, terminal report only.
