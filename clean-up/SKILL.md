---
name: clean-up
description: Use when a completed branch needs a senior pre-PR audit for bugs, missed reuse, unnecessary complexity, or missing regression tests, with valid findings fixed.
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
- Runtime acceptance testing (use `/qa-ticket`); use `opening-prs` only when a separate pull-request workflow is explicitly requested

## Step 1: Resolve the input

The skill accepts:
- A branch name (e.g., `feature/proj-883-foo`)
- A ticket ID (e.g., `PROJ-883`, `ABC-123`)
- Nothing — operate on the current branch

Resolution order:

1. If the argument matches a ticket pattern (`[A-Z]+-\d+`), look up the canonical branch via the platform CLI:
   ```bash
   linear api 'query { issue(id: "<TICKET-ID>") { branchName } }'
   ```
   If the branch doesn't exist locally, `git fetch origin` first, then expect `origin/<branchName>`.

2. If the argument looks like a branch name, use it directly.

3. If no argument, use `git branch --show-current`.

If target evidence is ambiguous, stop before review or mutation and report the candidate facts: each candidate branch or ticket, its source, head, base, associated PR metadata, and the exact conflicting evidence. Do not silently choose a candidate; do not ask the user to select one during this run. Continue only after a later explicit invocation supplies an unambiguous target.

## Step 2: Identify the diff

The base branch is what the diff compares against. Detect it in this order:

1. If there's an open PR, resolve its PR metadata (number, forge, state, head, and `baseRefName`) with the available forge tooling; for GitHub, read `baseRefName` with `gh pr list --head <branch> --json baseRefName | jq -r '.[0].baseRefName'`.
2. Otherwise, fall back to the merge-base with the project's default branch (`develop` or `main`).
3. For stacked PRs, the base is the parent branch's head (e.g., `proj-709/backend-schemas`), NOT `develop`. Read the parent PR metadata with the available forge tooling when a stack is in play, including `baseRefName`; do not infer a stacked base from `develop`.

Print the resolved diff stats so the user sees the scope:
```bash
git log --oneline <base>..<head>
git diff --stat <base>..<head>
```

If the diff exceeds 2,000 changed lines, retain the full scope in the review ledger and partition it automatically into coherent slices by ownership and risk. Process the highest-risk slice first, then continue through the remaining slices without pausing for routine scope selection. Record every unprocessed file and finding as remaining scope for the final handoff.

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

Aggregate all four agent reports. Apply these priority rules consistently:

- **[P0] and [P1]**: Always fix if valid. These block merge.
- **[P2] and [P3]**: Fix if straightforward. Skip if it would balloon scope into a separate refactor.

Think critically before accepting any finding. The agents can be wrong. If you disagree, skip the finding and explain why in the final summary.

The invocation is authority for valid in-scope fixes and focused commits. Decide each finding immediately as a fix, follow-up, or skip, and record the reason in the triage ledger. Do not pause for routine approval or ask the user to choose a scope; stop only for a genuine blocker such as destructive recovery, missing authority, or work outside the invoked branch or ticket.

For each accepted finding, decide:
- **Fix in this skill run** (P0/P1 + small P2/P3)
- **File a follow-up ticket** (large P2/P3 refactors, cross-module changes the user should approve separately)
- **Skip** (false positive or out of scope)

For a large diff, execute accepted findings in risk-first coherent slices and retain the complete accepted, skipped, follow-up, and unprocessed-scope record for handoff.

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
- Read the project's `CLAUDE.md` — it often documents canonical helpers and pitfalls (e.g., PROJ-615 / REF-004 in this repo)

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

The skill must not push, must not open a pull request, and must not merge. End by:
- Printing the commit log: `git log --oneline <base>..HEAD`
- Printing the test status (last `pytest` / `npm test` summary)
- Listing skipped findings, filed follow-up tickets, and remaining or unprocessed scope (if any)
- Saying which branch the user should `git switch` to in order to review

When the branch is ready, hand it back to the human with `opening-prs` as the retained pull-request workflow; this skill itself never creates the pull request.

## Common pitfalls

- **Pre-commit reformatter dance** — Many projects' pre-commit hooks (ruff, biome, prettier) edit files during the commit. The commit "fails" silently because the working tree is now dirty post-fix. Re-stage and re-run the commit. Don't bypass with `--no-verify`.
- **Pre-existing test failures on the base branch** — Some failing tests aren't yours. Before assuming a regression, run the failing test against `<base>` to see if it was already broken. If yes, surface it to the user but don't try to fix it in this run.
- **Stacked PR base detection** — `git merge-base HEAD develop` is wrong when the branch is stacked. Use the PR's `baseRefName` from `gh pr view`.
- **Beanie / ORM expression mocking is brittle** — Tests that introspect query argument shapes break when the ORM updates. Prefer behavioral tests (assert the right SKU is selected) over implementation tests (assert `find()` was called with X args).
- **"It's just one line" creep** — When a finding's fix accidentally needs three other changes, stop. File a follow-up and revert. The skill produces small, reviewable commits — that's the value.

## Why this skill exists

Vibe-coded branches commonly ship with a specific failure mode: the description and tests agree on what *should* happen, but the implementation drifts. Reviewing such branches by hand is slow because each finding requires its own context-switch (diff → test → fix → verify). This skill compresses that loop by parallelising the review and serialising the fixes — and by enforcing TDD on each fix, it leaves a regression test behind for every bug class that's been resolved, so the same drift can't sneak back in next time.
