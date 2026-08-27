# Opening Informative Pull Requests — Skill Design

**Date:** 2026-08-26  
**Status:** Approved design; awaiting written-spec review

## Purpose

Create one portable `opening-prs` skill that replaces the duplicated behavior in Mondrio's Claude-only `frontend-pr` and `be-pr` commands. The skill prepares and opens an informative pull request that lets a reviewer understand the value, implementation, risks, and verification without reconstructing the change from the diff.

The first version is PR-only. Commit creation and splitting remain the responsibility of `atomic-commit` or the user. The existing Mondrio commands remain unchanged during this change.

## Invocation and portability

`opening-prs` will be model-invoked when a user asks to open, create, prepare, or draft an informative pull request for a completed branch.

The skill will use tool-neutral actions and repository-discovered conventions. It will not hard-code Claude, GitHub, Mondrio ticket syntax, `develop`, or a particular agent attribution. Repository instructions and the repository's canonical pull-request template override generic defaults.

## Workflow

### 1. Establish the PR target

Read repository instructions, forge metadata, the canonical pull-request template, branch state, remotes, recent history, and the likely base branch. Establish one base/head comparison and record the target repository, base, head, and forge.

A protected/default branch or ambiguous base requires clarification. A dirty worktree stops the PR workflow and directs the user to commit the intended changes, using `atomic-commit` when appropriate. The completion criterion is an unambiguous committed branch and base/head range.

### 2. Reconstruct the change from evidence

Inspect the complete base-to-head diff and relevant surrounding code. Treat ticket text, prior summaries, and agent memory as claims rather than evidence. Account for every changed file and classify the change's impact dimensions:

- visible frontend/UI behavior
- frontend state, routing, or data flow
- backend/API behavior
- data, migrations, indexes, or compatibility
- infrastructure, configuration, dependencies, or rollout
- tests, documentation, or internal refactoring

Mixed changes use every applicable branch. The completion criterion is that every changed file and every material reviewer concern is represented in the PR draft or explicitly judged immaterial.

### 3. Gather verification evidence

Use repository-defined commands to run the smallest targeted checks that exercise the changed behavior. Prefer changed tests and focused lint/type checks over an unrelated full suite. Preserve exact commands and observed outcomes.

For visible UI changes, require screenshot or recording evidence. If the agent cannot capture it, the draft states that it is missing and creation pauses for the user rather than inventing evidence. For backend/API changes, include concrete executed tests and runnable request examples only when they help reviewers reproduce the behavior. Unrun checks remain explicitly unverified.

The completion criterion is a truthful verification record covering the highest-risk changed behavior, or a clearly stated blocker that prevents PR creation.

### 4. Compose the reviewer brief

The repository template is the output schema. Fill every applicable section with evidence and remove comments, examples, and unused optional sections. If no template exists, use this fallback structure:

1. Summary
2. Customer/user value
3. What changed
4. Why
5. Architecture or flow, only when it clarifies at least three meaningful interactions or transitions
6. What reviewers need to know: decisions, trade-offs, compatibility, data/infra impact, and gotchas
7. Test plan with exact observed evidence
8. Screenshots or recordings when UI-visible
9. Out of scope
10. Applicable checklist

The title follows repository conventions; otherwise use a concise Conventional Commit-style title. Ticket IDs are inferred only from reliable repository or branch evidence.

The draft must contain no placeholders and no runtime-specific attribution. The completion criterion is that a reviewer coming in cold can identify the change's value, load-bearing implementation, risks, and verification from the title and body.

### 5. Approval and external side effects

Present the proposed forge, base, title, body, verification summary, and any missing evidence before pushing or creating the PR. Require explicit user approval.

After approval, perform a normal non-force push when needed, create the PR with available forge tooling, and return the stable PR URL. A push or forge failure stops the workflow and reports the exact failure without destructive recovery.

## Skill shape

The initial skill will be a single `opening-prs/SKILL.md`. Frontend and backend behavior are conditional branches in one process, not separate skills or duplicated reference files. Additional reference files are justified only if testing shows genuine sprawl or a branch that most invocations do not need.

The description will contain invocation conditions only. The body will use a compact sequence with checkable completion criteria, a quick impact-to-evidence table, a fallback PR contract, and common failure modes.

## Validation strategy

Skill creation follows RED–GREEN–REFACTOR:

1. Run baseline pressure/application scenarios without the skill and capture failures such as generic summaries, invented verification, backend-only or frontend-only assumptions, placeholder leakage, premature PR creation, or hard-coded tooling.
2. Add the minimal skill guidance that corrects observed failures.
3. Re-run the same scenarios with the skill and tighten only demonstrated gaps.
4. Add repository tests for routing metadata, required behavioral contracts, catalog synchronization, and skill quality.
5. Run the focused tests and the complete repository test suite before completion.

## Out of scope

- Creating, amending, splitting, or rewriting commits
- Force pushing or destructive Git recovery
- Reviewing the code for approval or fixing findings
- Posting comments to an existing PR
- Removing the two Mondrio `.claude/commands` files in this change
- Embedding Mondrio-specific ticket, base-branch, or forge conventions in the portable skill
