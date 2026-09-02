# Skills

Carlos's portable development workflow for Claude Code, Codex, Pi, and OMP.

## Workflow

Start at the first step the work still needs. Most tickets do not need every
skill.

```text
prep-ticket → exec-ticket → qa-ticket → clean-up
            → atomic-commit → opening-prs → pr-sweep
```

- Use `check-data` when QA needs local records.
- Use `blast-radius` for a known risk outside the diff.
- Use `interrogate` when independent reviewers should search for unknown risks.
- Use the verification skills to create or maintain reusable real-app checks.

See [WORKFLOW.md](WORKFLOW.md) for entry points, optional steps, and high-risk
workflows.

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
