# Skills

Claude Code skills for development workflows.

## Skills

| Skill | Description |
|-------|-------------|
| `atomic-commit` | Splits git changes into logical atomic commits using conventional commits |
| `prep-ticket` | Prepares a developer for a Linear/Jira ticket — fetches context, checks blockers, scans codebase |
| `check-data` | Audits the local DB and plans the data needed to QA the current branch — happy / edge / error / stupid paths; writes a markdown plan |
| `qa-ticket` | Automates QA testing for the current branch against localhost using ticket context |
| `pi-review` | Handles code review findings from [Pi](https://github.com/carlosarraes/pi-review) received via tmux |

## Install

```bash
# all skills
./add all

# specific skill
./add atomic-commit
```

Skills are symlinked to `~/.claude/skills/` and `~/.agents/skills/`.
