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
| `orchestrate` | Coordinates broad work through checkpointed skills, agents, worktrees, Codex, QA, and PR-watch workflows |
| `pi-review` | Handles code review findings from [Pi](https://github.com/carlosarraes/pi-review) received via tmux |
| `pr-sweep` | Monitors open PRs on a 10-min self-pacing loop and auto-fixes CI failures, merge conflicts, and bot AND human review comments; skips quiet PRs via a state file |
| `exec-ticket` | Implements the agreed plan for the current branch's ticket, test-first and YAGNI-biased |
| `review-swarm` | Runs independent perspective reviewers (qa-team, security, generalist, carraes) in parallel and posts convergent findings + a sticky verdict to a PR |
| `qa-team` | Multi-agent QA review: parallel specialist + generalist agents review a diff against real incident patterns and converge on a verdict |
| `stamp-check` | Low-risk PR approval gate — deterministic gates (state, deny-list, size) before an LLM showstopper scan; approves only after explicit confirm |
| `split-pr` | Decomposes an oversized branch into a bottom-up stack of small, independently-runnable PRs (native git + gh) |
| `qa-pr` | Outward sibling of `qa-ticket` — runs acceptance testing against a PR and posts one sticky evidence comment (screenshots/GIFs) so reviewers observe behavior |
| `carraes-reviewer` | Code reviewer in Carlos's voice and priorities; plugs into `review-swarm` (draft — pending mined review history) |

## Install

```bash
# all skills
./add all

# specific skill
./add atomic-commit
```

Skills are symlinked to `~/.claude/skills/` and `~/.agents/skills/`.
