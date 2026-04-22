# Skills

Claude Code skills for development workflows.

## Skills

| Skill | Description |
|-------|-------------|
| `atomic-commit` | Splits git changes into logical atomic commits using conventional commits |
| `prep-ticket` | Prepares a developer for a Linear/Jira ticket — fetches context, checks blockers, scans codebase |
| `qa-ticket` | Automates QA testing for the current branch against localhost using ticket context |
| `pi-review` | Handles code review findings from [Pi](https://github.com/carlosarraes/pi-review) received via tmux |
| `fix-review` | Applies PR review comments as atomic, one-commit-per-comment fixes (paste / `gh` / `bt`) |

## Install

```bash
# all skills
./add all

# specific skill
./add atomic-commit
```

Skills are symlinked to `~/.claude/skills/` and `~/.agents/skills/`.
