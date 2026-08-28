# Skills

Carlos's portable development workflow for Claude Code, Codex, Pi, and OMP.

## Workflow

This is a toolbox, not a mode. Start at the first step the work still needs and
skip anything that does not apply.

1. **Intake**: use Matt Pocock's external `triage` for a reported bug, or
   `triage-incident` when a production symptom needs an evidence-backed verdict.
2. **Prepare**: `prep-ticket`; let external `codebase-design` or
   `domain-modeling` join only when the module boundary or domain shape is part
   of the problem.
3. **Build**: `exec-ticket` with the installed TDD owner. It now carries the
   useful pstack rules for observable outcomes, idempotency, shared-state
   ownership, caller migration, and executable regression protection.
4. **Prove**: create a repo-local real-app harness once with
   `create-verification-skill`, refresh it periodically with
   `maintain-verification-skill`, and use `check-data` → `qa-ticket` for the
   current branch.
5. **Review**: `clean-up`; add externally maintained `blast-radius` for
   beyond-diff risk, or invoke `interrogate` for an expensive adversarial pass.
6. **Ship**: `atomic-commit` → `opening-prs` [`gitflow`] → `pr-sweep`.

`split-pr` may trigger automatically for Mondrio above 1,000 changed lines.
`qa-team`, `carraes-reviewer`, `simplification-audit`, `video-extract`, and the
three ported pstack skills are explicit tools, not routine steps.

### Pstack decisions

- **Maintained externally**: `blast-radius`, `show-me-your-work`, and `unslop`.
- **Ported here**: `create-verification-skill`,
  `maintain-verification-skill`, and `interrogate`.
- **Adopted externally**: `typescript-best-practices`.
- **Adapted, not installed as fragments**: the 14 approved architecture and
  execution principles. Existing owners apply them when relevant; there is no
  auto-invoked principle router or `poteto-mode`.
- **Removed**: `no-comments`. The existing cleanup and review stack covers the
  useful behavior without its unavailable named-agent dependency.

The adapted principles live at their natural decision points:

| Owner | Principle responsibility |
| --- | --- |
| `prep-ticket` and external `codebase-design` | Foundations, domain shape, boundary and type discipline |
| `exec-ticket` | Outcomes, idempotency, shared state, caller migration, executable lessons, and justified leverage |
| `clean-up` and `interrogate` | Reader load, subtraction, first-principles challenges, and integrated architecture review |

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
