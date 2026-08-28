# Skills

Claude Code skills for development workflows.

## Workflow

The catalog follows four workflows. Model-visible skills can be selected from a
request; user-only skills run only as explicit commands.

- **Build**: `prep-ticket` → `exec-ticket` → `clean-up`
- **QA**: `check-data` → `qa-ticket`; `qa-team` only when explicitly invoked
- **Ship**: `atomic-commit` → `opening-prs` [gitflow] → `pr-sweep`
- **Utilities**: `split-pr` and `triage-incident` are automatic; `carraes-reviewer`, `simplification-audit`, and `video-extract` are explicit commands

Each step is optional — jump in wherever your ticket already is.

## Skills

<!-- SKILL-CATALOG:START -->
| Skill | Description |
|-------|-------------|
| `atomic-commit` | Use when the user asks to commit changes and the worktree contains multiple logical concerns that should become focused conventional commits. |
| `carraes-reviewer` | Use only when explicitly invoked to review a PR or diff in Carlos Arraes's voice. |
| `check-data` | Use when planning and loading schema-aware local database rows for branch or ticket QA, with optional plan-only mode. |
| `clean-up` | Use when a completed branch needs a senior pre-PR audit for bugs, missed reuse, unnecessary complexity, or missing regression tests, with valid findings fixed. |
| `create-verification-skill` | Use only when explicitly invoked to create a project-local verification skill for a real UI, CLI, service, desktop app, mobile app, or library. |
| `exec-ticket` | Use when the user wants an agreed ticket plan implemented on the current branch with test-driven, minimal changes. |
| `interrogate` | Use only when explicitly invoked for an adversarial multi-reviewer challenge of a diff, branch, pull request, design, or selected code. |
| `maintain-verification-skill` | Use only when explicitly invoked to audit and repair a project-local verification skill and its user-facing feature map. |
| `opening-prs` | Use when the user wants to open, create, prepare, or draft an informative pull request for a completed branch. |
| `pr-sweep` | Use when open non-draft PRs need ongoing convergence to mergeability across CI, conflicts, size gates, bot feedback, and human review. |
| `prep-ticket` | Use when preparing to implement a Linear or Jira ticket by gathering context, blockers, related work, code entry points, and unanswered questions. |
| `qa-team` | Use only when explicitly invoked for a comprehensive multi-agent QA code review. |
| `qa-ticket` | Use when the current ticket branch needs executable acceptance or smoke testing against a local backend or frontend, including fix-and-retry. |
| `simplification-audit` | Use only when explicitly invoked for a whole-codebase simplification audit. |
| `split-pr` | Use when directly invoked to split an oversized PR or branch, or when enforced repository size limits are exceeded; trigger automatically for Mondrio over 1,000 changed lines. |
| `triage-incident` | Use when a production or staging symptom, alert, or stakeholder report needs a read-only evidence-backed bug-versus-expected-behavior verdict. |
| `video-extract` | Use only when explicitly invoked to extract clean transcripts from YouTube videos. |
<!-- SKILL-CATALOG:END -->

## Install

```bash
# all skills
./add all

# specific skill
./add atomic-commit
```

Skills are symlinked to `~/.claude/skills/` and `~/.agents/skills/`.
