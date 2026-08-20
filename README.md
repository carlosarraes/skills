# Skills

Claude Code skills for development workflows.

## Workflow

Most skills chain into a ticket pipeline; the rest are standalone review/utility tools.

- **Build**: `prep-ticket` → *grill the design* → `change-contract` → `exec-ticket` → `check-contract` → `clean-up`
- **QA**: `check-data` → `seed-data` → `qa-ticket` (+ `chaos-engineering` for hostile testing) → `qa-evidence`
- **Ship**: `atomic-commit` → `ship-gitflow`, with `qa-pr` leaving acceptance evidence on the PR
- **Review** (someone else's change): `diff-brief` to triage → `qa-team` / `review-swarm` / `stamp-check` to judge → `split-pr` if too big → `pr-sweep` to drive PRs to merge

Each step is optional — jump in wherever your ticket already is.

## Skills

<!-- SKILL-CATALOG:START -->
| Skill | Description |
|-------|-------------|
| `atomic-commit` | Use when the user asks to commit changes and the worktree contains multiple logical concerns that should become focused conventional commits. |
| `carraes-reviewer` | Use when reviewing a PR or diff in Carlos Arraes's voice, applying his evidence-led priorities and team-appropriate register. |
| `change-contract` | Use when a ticket design is settled and needs an explicitly approved, immutable implementation contract before coding. |
| `chaos-engineering` | Use when a locally running, feature-complete branch needs resilience, abuse, fuzz, race, dependency-failure, or adversarial testing after its happy path works. |
| `check-contract` | Use when the user explicitly asks to audit completed implementation against an approved change contract, including drift, YAGNI, and reuse. |
| `check-data` | Use when planning the local database rows needed to QA a branch or ticket before seeding or acceptance testing. |
| `clean-up` | Use when a completed branch needs a senior pre-PR audit for bugs, missed reuse, unnecessary complexity, or missing regression tests, with valid findings fixed. |
| `diff-brief` | Use when an arbitrary PR, branch, commit, or range—especially someone else's change—needs a diff brief, change summary, risk map, or fast review triage. |
| `exec-ticket` | Use when the user wants an agreed ticket design or approved change contract implemented on the current branch. |
| `explain-diff` | Use when the user wants to deeply understand a subsystem or code change—not merely review it—through an interactive teaching walkthrough. |
| `orchestrate` | Use when a broad workflow spans multiple independent tickets, PRs, phases, worktrees, or agents and needs coordinated checkpoints. |
| `oss-scout` | Use when searching for open-source repositories that genuinely need contributors or approachable, unclaimed issues in a chosen technical area. |
| `oss-scout-issues` | Use when choosing a contribution issue inside a known open-source repository, ranking candidates by feasibility, competition, and career value. |
| `pi-review` | Use when review findings arrive from Pi through its findings marker, priority-tagged verdicts, tmux, or session-control and must be handled. |
| `pr-sweep` | Use when open non-draft PRs need ongoing convergence to mergeability across CI, conflicts, size gates, bot feedback, and human review. |
| `prep-ticket` | Use when preparing to implement a Linear or Jira ticket by gathering context, blockers, related work, code entry points, and unanswered questions. |
| `qa-evidence` | Use when completed QA results for a ticket must be recorded in the team QA spreadsheet. |
| `qa-pr` | Use when the user wants to QA a GitHub or Bitbucket PR and leave observable acceptance-test evidence on the PR for reviewers. |
| `qa-team` | Use when the user asks for a multi-agent QA review team or comprehensive QA-team code review of a branch or diff, rather than acceptance testing. |
| `qa-ticket` | Use when the current ticket branch needs executable acceptance or smoke testing against a local backend or frontend, including fix-and-retry. |
| `review-swarm` | Use when the user asks for a review swarm, swarm review, or full multi-perspective swarm review of a PR or branch. |
| `seed-data` | Use when an existing check-data plan must be inserted into the local database before QA. |
| `ship-gitflow` | Use when a completed ticket must ship through the twin production and staging Bitbucket branch, PR, and pipeline flow, or one leg needs completion. |
| `simplification-audit` | Use when the user wants a whole-codebase simplification audit of data structures, state representation, control flow, algorithms, or ownership, rather than a branch review, general risk audit, or implementation. |
| `split-pr` | Use when a PR or branch is too large to review safely and should become a stack of small, independently runnable and mergeable PRs. |
| `stamp-check` | Use when deciding whether a teammate's small, low-risk PR is safe to approve, with explicit confirmation required before posting approval. |
| `triage-incident` | Use when a production or staging symptom, alert, or stakeholder report needs a read-only evidence-backed bug-versus-expected-behavior verdict. |
| `video-extract` | Use when the user needs clean transcripts from one or more YouTube videos, including captionless videos that may require transcription. |
<!-- SKILL-CATALOG:END -->

## Install

```bash
# all skills
./add all

# specific skill
./add atomic-commit
```

Skills are symlinked to `~/.claude/skills/` and `~/.agents/skills/`.
