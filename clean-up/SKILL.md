---
name: clean-up
description: "Audit a branch for bugs, code-reuse misses, quality issues, and missing regression tests, then fix valid findings test-first (one focused commit per finding) and finish with /simplify. Use when the user says 'clean up this branch', 'clean up <ticket>', '/clean-up', 'audit this branch', 'review and refactor my branch', 'sanity-check before PR', 'tidy up before merge', or 'find latent bugs in my branch'. Targets vibe-coded branches that need a senior-engineer pass before merge — dispatches parallel review agents, leans on existing helpers before adding abstractions, and never auto-pushes or opens a PR. Accepts a branch name or ticket ID (e.g., 'clean up feature/foo' or 'clean up MON-883'); operates on the current branch if neither is given."
---

# Clean-up: branch review + TDD refactor

End-to-end pass that turns a "works on my machine" feature branch into something you'd defend in code review. Mirrors the workflow a senior engineer runs by hand: scope the diff, dispatch parallel review agents, triage the findings, fix each one test-first, lean on existing helpers, run `/simplify` on the cumulative diff, hand back to the human to push and PR.

## When to use this skill

Trigger when:
- The user wants a quality pass before opening a PR or pushing
- A vibe-coded branch needs a senior review (descriptions claim things the code doesn't do)
- An external review (Pi, qodo, human reviewer) flagged findings to address
- The user explicitly says "clean up", "audit", "tidy up", "/clean-up"

Do NOT use for:
- Pure feature implementation (use TDD directly)
- One-line typo fixes (just edit and commit)
- Operations that need a different skill — `/qa-ticket` for runtime testing, `/be-pr` or `/frontend-pr` for opening PRs, `/pi-review` for handling Pi findings

## Step 1: Resolve the input

The skill accepts:
- A branch name (e.g., `feature/mon-883-foo`)
- A ticket ID (e.g., `MON-883`, `ABC-123`)
- Nothing — operate on the current branch

Resolution order:

1. If the argument matches a ticket pattern (`[A-Z]+-\d+`), look up the canonical branch via the platform CLI:
   ```bash
   linear api 'query { issue(id: "<TICKET-ID>") { branchName } }'
   ```
   If the branch doesn't exist locally, `git fetch origin` first, then expect `origin/<branchName>`.

2. If the argument looks like a branch name, use it directly.

3. If no argument, use `git branch --show-current`.

Confirm the resolved branch with the user before continuing if you had to disambiguate.

## Step 2: Identify the diff

The base branch is what the diff compares against. Detect it in this order:

1. If there's an open PR, read its `baseRefName`: `gh pr list --head <branch> --json baseRefName | jq -r '.[0].baseRefName'`.
2. Otherwise, fall back to the merge-base with the project's default branch (`develop` or `main`).
3. For stacked PRs, the base is the parent branch's head (e.g., `mon-709/backend-schemas`), NOT `develop`. Always confirm with `gh pr view <PR> --json baseRefName` when a stack is in play.

Print the resolved diff stats so the user sees the scope:
```bash
git log --oneline <base>..<head>
git diff --stat <base>..<head>
```

If the diff is enormous (>2000 LOC), warn the user and offer to scope to a subset before continuing.

## Step 3: Dispatch parallel review agents

Spawn **four review agents in parallel** in a single message — they're independent and don't share state. Pass each agent the worktree path (or main repo path), the base→head range, and a focused prompt.

| Agent | Focus | What to look for |
|---|---|---|
| **Code reuse** | Find existing helpers, dedup opportunities | Functions that duplicate utilities elsewhere; inline patterns repeated 3+ times that should become a helper; sibling routers/modules doing the same thing with drift |
| **Code quality** | KISS, leaky abstractions, copy-paste | Parameter sprawl, premature abstractions, copy-paste with slight variation, stringly-typed code, unnecessary nesting, comments explaining WHAT instead of WHY |
| **Efficiency** | Hot path, n+1, redundant work | New blocking work in startup/per-request paths, sequential operations that could be parallel, unbounded data structures, recurring no-op state writes |
| **Coverage** | TDD / regression-test compliance | Functions/branches without tests, claimed-fixed bugs without a regression test, test files that only assert happy paths |

Each agent must return findings with: **severity (P0/P1/P2/P3), file:line, issue, why it matters, suggested fix**.

Word cap each agent at ~600 words so the synthesis stays scannable.

## Step 4: Triage findings

Aggregate all four agent reports. Apply the same priority rules as `/pi-review`:

- **[P0] and [P1]**: Always fix if valid. These block merge.
- **[P2] and [P3]**: Fix if straightforward. Skip if it would balloon scope into a separate refactor.

Think critically before accepting any finding. The agents can be wrong. If you disagree, skip the finding and explain why in the user-facing summary.

For each accepted finding, decide:
- **Fix in this skill run** (P0/P1 + small P2/P3)
- **File a follow-up ticket** (large P2/P3 refactors, cross-module changes the user should approve separately)
- **Skip** (false positive or out of scope)

Show the triage to the user before fixing if the list is non-trivial (>3 items). Let them adjust.

## Step 5: Apply fixes using TDD

For each in-scope finding, run a strict TDD cycle:

1. **RED** — Write a regression test that captures the correct behavior. Run it. Confirm it fails for the expected reason (missing feature / wrong output / exception). If the test passes immediately, you wrote the wrong test.
2. **GREEN** — Apply the minimal code change to make the test pass. No drive-by refactors.
3. **Verify** — Run the relevant test file or directory. Make sure no other tests regressed.
4. **Commit** — One focused commit per finding (see Step 6).

If a fix is a pure refactor (no behavior change), you don't need a new RED test — but the existing test suite must still be green before AND after. Run it both times.

If you can't write a test for a finding (e.g., it requires DB transaction infra you don't have), say so explicitly and propose how it'll be tested later. Don't skip silently.

## Step 6: Commit discipline

One commit per finding. Each commit must:
- Be staged by explicit path (`git add path/to/file`), never `git add -A` or `git add .`
- Use Conventional Commits format. Check the project's `CLAUDE.md` for the local convention; if absent, use `<type>(<scope>): <description> (TICKET-ID)` where type ∈ {feat, fix, refactor, docs, style, test, chore}.
- Explain the **WHY** in the message body. The reviewer should understand the bug class without re-reading the diff.
- Pass pre-commit hooks. If hooks reformat files, re-stage and commit again — do not bypass with `--no-verify`.
- Never include unrelated changes. If you notice something else broken, file it as a follow-up; don't bundle.

Why one-per-finding: lets the human (and any review bot) re-review commit-by-commit, run `git bisect` against a single conceptual change, and revert one fix without losing others.

## Step 7: Leverage existing code

Before introducing a new helper, search the codebase for an analogous one:
- Look in `<project>/shared/`, `<module>/utils.py`, sibling modules
- Search for patterns like `merge_*`, `validate_*`, `_build_*_payload`
- Read the project's `CLAUDE.md` — it often documents canonical helpers and pitfalls (e.g., MON-615 / RT-004 in this repo)

If 3+ inline duplicates exist, extracting to a single helper is justified. If only 1-2, KISS — leave the duplication. The "rule of three" is a sanity check, not a mandate.

When the same helper would benefit other modules you didn't change in this run, file a follow-up ticket; don't expand scope mid-clean-up.

## Step 8: When to invoke /find-skills

Some findings need capabilities the agent doesn't have. If you hit one of these, run `/find-skills` to discover whether an installable skill addresses it:
- "We need a typed code-review pass" → could match a code-review skill
- "We need to wire a CI lint" → could match a CI/lint skill
- "We need to scaffold a typed mock" → could match a testing skill

Run `/find-skills` BEFORE writing custom logic for the missing capability. If a relevant skill exists, install and invoke it. If not, fall back to the manual approach.

## Step 9: Final pass — invoke /simplify

After all per-finding commits, invoke `/simplify` on the cumulative diff:
```bash
git diff <base>..HEAD
```

`/simplify` runs three more parallel agents (reuse, quality, efficiency) over the full delta. It catches things the per-finding lens misses — patterns that emerge only when looking at the change as a whole (e.g., "you added a helper here and an inline version of the same logic over there").

Apply only the in-scope `/simplify` recommendations (P0/P1 + small P2). File the rest as follow-ups.

## Step 10: Stop and hand back

The skill MUST NOT push, force-push, open a PR, or merge. End by:
- Printing the commit log: `git log --oneline <base>..HEAD`
- Printing the test status (last `pytest` / `npm test` summary)
- Listing skipped findings + filed follow-up tickets (if any)
- Saying which branch the user should `git switch` to in order to review

The user runs `/be-pr`, `/frontend-pr`, or their preferred PR command when they're satisfied.

## Common pitfalls

- **Pre-commit reformatter dance** — Many projects' pre-commit hooks (ruff, biome, prettier) edit files during the commit. The commit "fails" silently because the working tree is now dirty post-fix. Re-stage and re-run the commit. Don't bypass with `--no-verify`.
- **Pre-existing test failures on the base branch** — Some failing tests aren't yours. Before assuming a regression, run the failing test against `<base>` to see if it was already broken. If yes, surface it to the user but don't try to fix it in this run.
- **Stacked PR base detection** — `git merge-base HEAD develop` is wrong when the branch is stacked. Use the PR's `baseRefName` from `gh pr view`.
- **Beanie / ORM expression mocking is brittle** — Tests that introspect query argument shapes break when the ORM updates. Prefer behavioral tests (assert the right SKU is selected) over implementation tests (assert `find()` was called with X args).
- **"It's just one line" creep** — When a finding's fix accidentally needs three other changes, stop. File a follow-up and revert. The skill produces small, reviewable commits — that's the value.

## Why this skill exists

Vibe-coded branches commonly ship with a specific failure mode: the description and tests agree on what *should* happen, but the implementation drifts. Reviewing such branches by hand is slow because each finding requires its own context-switch (diff → test → fix → verify). This skill compresses that loop by parallelising the review and serialising the fixes — and by enforcing TDD on each fix, it leaves a regression test behind for every bug class that's been resolved, so the same drift can't sneak back in next time.
