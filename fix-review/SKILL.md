---
name: fix-review
description: "Apply code review comments as atomic, one-commit-per-comment fixes with descriptive commit messages that explain WHY. Use this skill whenever the user says 'fix review', 'fix-review', 'address review comments', 'apply review suggestions', 'handle these review comments', 'apply the feedback', or pastes PR review comments into the prompt asking for them to be addressed. Works with pasted comments, GitHub PRs (via `gh`), and Bitbucket PRs (via `bt`). Trigger whenever PR review feedback needs to be translated into focused, reviewable commits — even if the user only says 'fix the review' without specifying a source."
---

# Fix Review

Apply code review comments as focused, atomic commits — one commit per comment — so the reviewer can re-review commit-by-commit instead of re-reading a whole diff.

**Core principle:** Gather → plan → approval → one commit per comment. Skip comments that aren't straightforward fixes (disagree, too large, ambiguous) and report them at the end.

## Phase 1: Gather Comments

Detect sources in this order. Use whichever finds comments first.

### 1. Already in the prompt
If the user pasted review feedback into their message, use it. Look for numbered/bulleted suggestions, quoted snippets referencing files/lines, or GitHub `suggestion` blocks.

### 2. GitHub PR (if `gh` is available)
```bash
gh pr view --json number,title,url            # current branch's PR
gh api repos/{owner}/{repo}/pulls/{pr}/comments    # inline review comments
gh api repos/{owner}/{repo}/issues/{pr}/comments   # general PR comments
```
If multiple PRs match the branch, ask which one.

### 3. Bitbucket PR (if `bt` is available)
Use the `bt` skill to pull PR comments for the current branch.

### 4. Ask the user to paste
If none of the above find comments, say: *"Paste the review comments you want me to address."*

### Normalize
Parse each comment into `{id, file, line, text, author}`. Ignore approvals, LGTMs, pure questions without a requested change, and already-resolved threads.

## Phase 2: Analyze

For each comment:

1. **Confirm the issue** — read the referenced file and lines. The reviewer may have misread. Don't accept blindly.
2. **Classify:**
   - `fix` — valid and mechanical, will apply
   - `skip (disagree)` — note the reason
   - `skip (too large)` — would require a refactor out of scope for one commit
   - `skip (needs discussion)` — design call, not a mechanical fix
3. For `fix` entries, draft the change and a commit message that explains **why** the change is needed — the review comment's intent in a short line.

## Phase 3: Present the Plan

Show the full plan before touching any files:

```
## Fix-Review Plan

PR: <title + URL, if known>
Source: paste | gh | bt

| # | File:Line | Comment (excerpt) | Action | Commit message |
|---|-----------|-------------------|--------|----------------|
| 1 | src/auth.py:42 | "null check missing"      | fix      | fix: guard null session to prevent 500 on logout |
| 2 | src/api.ts:88  | "rename uid to userId"    | refactor | refactor: rename uid to userId for API consistency |
| 3 | README.md      | "typo 'teh'"              | docs     | docs: fix install-section typo |

Skipped:
- #4 src/utils.py:12 — "rewrite as one-liner" — disagree: loses null short-circuit
- #5 src/api.ts:200 — "switch to observables" — needs discussion: large API change
```

Then ask: **"Proceed with this plan? (yes / edit / abort)"**

- **yes** — execute
- **edit** — user adjusts which to apply, reorder, or tweak messages
- **abort** — stop, nothing modified

## Phase 4: Execute — One Commit Per Comment

For each approved entry, in order:

1. Apply ONLY the change the comment asks for — no collateral refactors, no unrelated tweaks
2. `git status && git diff` to confirm the diff is scoped to this one comment
3. Stage by explicit path (never `git add -A` or `git add .`)
4. Commit:
   ```bash
   git commit -m "$(cat <<'EOF'
   fix: message explaining why
   EOF
   )"
   ```
5. `git status` between commits — tree must be clean before the next fix

If a commit fails (pre-commit hook, test, lint):
1. Report the error
2. STOP — do not continue to the next comment
3. Ask the user whether to fix the underlying issue, amend, or abort

After all commits, show the result:
```bash
git log --oneline -N    # N = number of commits created
```

## Phase 5: Report

Summarize:
- How many fixes applied and the commit shortlog
- How many skipped and why (copy straight from the plan)
- Suggest the user reply on the PR describing what was fixed and what needs discussion — do NOT auto-reply on the PR

## Commit Message Rules

Follow the project's `CLAUDE.md` if present. Defaults:

- One line, conventional commits, **no scopes** (`fix:` not `fix(auth):`)
- Lowercase after the colon, no trailing period, under 72 chars
- **Explain WHY, not what** — the comment is the "why"; your message should capture its intent
  - Bad: `fix: update login function`
  - Bad: `fix: address review comment`
  - Good: `fix: guard null session to prevent 500 on logout`
  - Good: `refactor: rename uid to userId for API consistency`

| Type | Use for |
|------|---------|
| fix | Bug a reviewer caught |
| refactor | Rename, extract, restructure — no behavior change |
| perf | Performance improvement the reviewer suggested |
| docs | Comments, docstrings, README |
| test | Adding or fixing tests the reviewer requested |
| style | Formatting — only if the reviewer explicitly asked |
| chore | Config, deps, tooling |

## Safety Rules

**Never:**
- Combine multiple comments into one commit — defeats the whole purpose
- Auto-reply on the PR (GitHub, Bitbucket, etc.) — that's a human step
- Amend or rewrite previously-pushed commits
- Use `git add -A` / `git add .`
- Continue past a failing commit without user input
- Change code beyond what the comment explicitly requests

**Always:**
- Read the referenced file before drafting a fix
- Skip comments you can't validate — don't guess at intent
- Get approval on the plan before touching files
- Respect the project's `CLAUDE.md` commit conventions
- Stage files by explicit path

## Examples

**Comment:** *"This throws if `users` is undefined."*
- Fix: add `users?.length ?? 0` guard
- Commit: `fix: guard undefined users to prevent render crash`

**Comment:** *"Let's extract this block into a helper — it's used in two places."*
- Fix: extract function, update call sites in the same file
- Commit: `refactor: extract calcTax helper to remove duplication`

**Comment (nit):** *"Inconsistent quotes in this block."*
- Fix: normalize quotes in the referenced block only
- Commit: `style: use single quotes to match file convention`

**Comment:** *"Could this use `Promise.all`?"* — a question, not a requested change
- Action: `skip (needs discussion)` — respond on the PR instead

**Comment:** *"This whole module should be rewritten."* — scope too large for one commit
- Action: `skip (too large)` — flag for a follow-up ticket
