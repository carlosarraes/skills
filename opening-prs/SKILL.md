---
name: opening-prs
description: Use when the user wants to open, create, prepare, or draft an informative pull request for a completed branch.
---

# Opening pull requests

## Authority

This workflow opens a pull request only. It never creates, amends, splits, or rewrites commits; use `atomic-commit` when commit preparation is needed. Repository instructions and canonical pull-request template win over this guidance. Do not assume a forge, branch name, ticket syntax, runtime, or command: discover them from the repository and its remotes. Do not invent verification, attribution, or review evidence.

## 1. Establish the target

Read repository instructions, forge metadata, the canonical pull-request template, remotes, default/protected branches, recent history, current branch/head, and status. Establish exactly one base/head range and record repository, forge, remote, base, head, and status. Stop on a dirty worktree, a protected or default branch as the working head, or an ambiguous target; do not draft or publish. A dirty worktree is a handoff to `atomic-commit` when appropriate.

**Complete when:** The committed head, remote, and unambiguous base are recorded and the worktree is clean.

## 2. Reconstruct the change

Inspect the complete base/head diff, surrounding code, and history relevant to intent. Account for every changed file and classify each by reviewer impact: visible UI; frontend state, routing, or data flow; API or backend; data, migration, index, or compatibility; configuration, dependency, or rollout; and tests, docs, or refactoring. Derive the title and ticket only from reliable repository or branch evidence; otherwise use a concise outcome-focused title without guessing.

**Complete when:** Every changed file and material reviewer concern is represented in the draft or explicitly marked immaterial.

## 3. Verify the changed behavior

Select the smallest repository-defined checks covering the highest-risk behavior, then run them. Preserve exact commands and observed outcomes; unrun checks remain unverified. For visible UI, require a screenshot or recording of the changed behavior. If evidence cannot be captured, state that it is missing, do not invent verification, and ask the user to supply or unblock it; missing UI evidence pauses PR creation. For backend/API changes, include concrete executed tests or reproducible request evidence when useful.

**Complete when:** The record truthfully covers the highest-risk behavior, or states the blocker that prevents creation.

## 4. Draft the reviewer brief

Use the repository template as the schema, filling every applicable section and removing comments, examples, placeholders, and unused optional sections. Read the [fallback PR body](references/fallback-pr-body.md) only when no canonical template exists. Explain customer/user value, implementation, rationale, risks, compatibility, data/infra effects, and exact verification. Use Mermaid only for at least three material interactions or transitions. Do not include runtime-specific attribution.

**Complete when:** A cold reviewer can understand value, load-bearing changes, impact, and observed verification without reconstructing the diff.

## 5. Approve and create

Preview all of the forge, base, title, body, verification, and missing evidence. Require explicit approval before any external side effect. After approval, use a normal non-force push if needed, then the discovered forge tooling; never perform destructive recovery. Stop on push or creation failure and report the exact failure. On success, return the stable PR URL.

**Complete when:** Explicit approval precedes push and forge creation, and the stable URL or exact failure is returned.

## Quick impact map

| Tested impact | Required reviewer evidence |
|---|---|
| Visible UI | Screenshot or recording plus observed behavior and states |
| Frontend state, routing, or data flow | Focused tests and affected flow/transition |
| API or backend | Executed tests or reproducible request and compatibility notes |
| Data, migration, or index | Applied/tested migration or index evidence and data-risk notes |
| Configuration, dependency, or rollout | Exact config/dependency change, compatibility, and rollout/infra impact |

## Common mistakes

| Mistake | Positive correction |
|---|---|
| Guessing forge, base, or ticket details | Discover repository metadata and state uncertainty; never hard-code defaults. |
| Treating screenshots as optional for visible UI | Require the screenshot or recording; pause and ask the user to supply or unblock missing evidence. |
| Claiming checks passed without running them | Record exact commands and observed outcomes; label unrun checks unverified. |
| Drafting around a dirty worktree or changing commits | Stop immediately and hand commit preparation to `atomic-commit`; never create, amend, split, or rewrite commits. |
| Publishing before review | Preview forge, base, title, body, verification, and missing evidence, then obtain explicit approval. |
| Leaving generic placeholders in the body | Fill or remove every applicable template section with concise, reviewer-oriented evidence. |
