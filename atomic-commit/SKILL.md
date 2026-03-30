---
name: atomic-commit
description: "Split git changes into logical atomic commits using conventional commits. Use this skill whenever the user wants to 'commit my changes', 'make atomic commits', 'split my commits', 'break up my changes', 'commit everything', 'group my changes into commits', 'create conventional commits', or asks to commit staged/unstaged git changes as separate logical units. Even if the user just says 'commit' and there are multiple unrelated changes, this skill applies. Trigger on any committing scenario where changes could benefit from being split into focused, atomic units."
---

# Atomic Commit

Split staged and unstaged git changes into logical atomic commits using conventional commits format.

**Core principle:** Analyze → present the plan → get approval → commit. Never modify code.

## Phase 1: Analyze Changes

Run in parallel:

```bash
git status
git diff --staged
git diff
git log --oneline -10
```

If a project-level `CLAUDE.md` exists in the repo root, read it for commit conventions. Project-level rules override these defaults (except: never use scopes, always one-line messages).

For each changed file, note:
- Path and extension
- Change type: modified, added, deleted, renamed, binary
- Whether staged or unstaged
- Brief summary of what changed (from the diff)

**Always skip these files — never stage or commit them:**
- `TASKS.md`, `CHANGELOG.md`
- `.env`, `.env.*`, `credentials.*`, `*secret*`, `*.pem`, `*.key`

Flag binary files (images, fonts, compiled assets) with `[binary]` — include them in commits but mark them in the plan.

Track renames: if `git status` shows `renamed: old -> new`, keep both sides in one commit.

If there are no changes, report "Nothing to commit" and stop.

## Phase 2: Group Into Commits

### Grouping Rules (priority order)

1. **Feature unit** — component + its test + its styles/types/constants
2. **Refactor unit** — all files touched by a rename, move, or signature change
3. **Fix unit** — bug fix + test that verifies the fix
4. **Migration + model** — ORM migration files + the model changes that generated them
5. **Config/infra** — CI, Docker, linter config, dependency lock files changed for the same reason
6. **Docs** — documentation-only changes

### Separation Rules

- Never mix a feature with an unrelated fix
- Never mix refactoring with new functionality
- Never mix formatting/style changes with logic changes
- If a file could belong in two commits, place it where it has the strongest relationship

### Commit Ordering

Foundational changes first:
1. Dependencies / config
2. Refactors / renames
3. Core logic / models
4. Features
5. Tests
6. Documentation

### Large Changesets (15+ files)

Group more aggressively — fewer well-organized commits beat many tiny single-file commits. A commit with 5 related files is better than 5 one-file commits.

## Phase 3: Present the Plan

Display the full commit plan before executing anything:

```
## Commit Plan

| # | Type | Message | Files |
|---|------|---------|-------|
| 1 | feat | add user avatar upload endpoint | src/api/avatar.py, tests/test_avatar.py |
| 2 | fix  | correct timezone handling in scheduler | src/scheduler.py |
| 3 | chore | update eslint config for v9 | .eslintrc.js, package.json |

Skipped files (not committed):
- TASKS.md (excluded by policy)
- .env.local (secrets)
```

Then ask: **"Proceed with this commit plan? (yes / edit / abort)"**

- **yes** — execute as shown
- **edit** — ask which commits to merge, split, reorder, or re-message
- **abort** — stop without committing

Do NOT proceed without explicit approval.

## Phase 4: Execute Commits

For each commit in the approved plan:

```bash
git add path/to/file1 path/to/file2

git status

git commit -m "$(cat <<'EOF'
type: message here
EOF
)"
```

Run `git status` between each commit to verify staging is correct.

If a commit fails (hook failure, GPG issue, etc.):
1. Report the error
2. Stop — do NOT continue to the next commit
3. Ask the user how to proceed

After all commits, show the result:

```bash
git log --oneline -N
```

(where N = number of commits just created)

## Conventional Commits Format

**NEVER use scopes. No parentheses, no scope text, ever.**

Format: `type: lowercase description`

| Type | Use for |
|------|---------|
| feat | New functionality |
| fix | Bug fix |
| docs | Documentation only |
| refactor | Code restructuring, no behavior change |
| test | Adding or updating tests |
| chore | Dependencies, config, tooling |
| style | Formatting, whitespace, semicolons |
| perf | Performance improvement |
| ci | CI/CD pipeline changes |
| build | Build system changes |

Message rules:
- One line only — no body, no footer
- Lowercase everything after the colon
- Start with a verb: add, fix, update, remove, refactor, improve
- No period at the end
- Under 72 characters total

## Safety Rules

**Never:**
- Modify, create, or delete source code — if you spot issues, tell the user but do not fix them
- Use `git add .` or `git add -A`
- Commit without showing the plan first
- Commit `TASKS.md` or `CHANGELOG.md`
- Commit files that look like secrets
- Continue after a failed commit without user input
- Force push, amend previous commits, or run `git reset`/`git checkout --`/`git clean`

**Always:**
- Stage files by explicit path
- Run `git status` between commits
- Get user approval before executing the plan
- Respect project-level CLAUDE.md conventions if present
- Mark binary files with `[binary]` in the plan

## Examples

**Feature with test:**
```
feat: add password reset endpoint
Files: src/auth/reset.py, tests/test_reset.py, src/auth/urls.py
```

**Refactor spanning multiple files:**
```
refactor: rename UserService to AccountService
Files: src/services/account.py, src/api/views.py, tests/test_account.py
```

**Mixed changeset → 3 commits:**
```
1. fix: correct null check in payment processor
   Files: src/payments/processor.py, tests/test_processor.py

2. feat: add dark mode toggle to settings page
   Files: src/components/Settings.tsx, src/styles/theme.css

3. chore: upgrade pytest to 8.1
   Files: requirements.txt, requirements-dev.txt
```
