# Skills

Claude Code skills for development workflows.

## Skills

| Skill | Description |
|-------|-------------|
| `atomic-commit` | Splits git changes into logical atomic commits using conventional commits |
| `prep-ticket` | Prepares a developer for a Linear/Jira ticket — fetches context, checks blockers, scans codebase |
| `check-data` | Audits the local DB and plans the data needed to QA the current branch — happy / edge / error / stupid paths; writes a markdown plan |
| `seed-data` | Reads the plan from `check-data` and inserts the rows via the project's preferred mechanism (seed script, ORM shell, raw SQL, or API) |
| `qa-ticket` | Automates QA testing for the current branch against localhost using ticket context |
| `chaos-engineering` | Stress-tests the current branch by injecting application-level chaos — input / auth / state / dependency / resource / frontend / time — and auto-fixes resilience violations test-first |
| `pi-review` | Handles code review findings from [Pi](https://github.com/carlosarraes/pi-review) received via tmux |
| `pr-sweep` | Monitors open PRs on a 10-min self-pacing loop and auto-fixes CI failures, merge conflicts, and bot review comments (Greptile, Cursor BugBot) |
| `pr-skill-fix` | Handles HUMAN reviewer feedback on open PRs — fix-here vs follow-up triage for APPROVED nits, silent fixes for CHANGES_REQUESTED overall bodies, threaded fix+reply+resolve for inline comments, then re-requests review |

## Install

```bash
# all skills
./add all

# specific skill
./add atomic-commit
```

Skills are symlinked to `~/.claude/skills/` and `~/.agents/skills/`.
