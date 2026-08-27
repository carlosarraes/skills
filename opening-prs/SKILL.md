---
name: opening-prs
description: Use when the user wants to open, create, prepare, or draft an informative pull request for a completed branch.
---

# Opening pull requests

## Authority

This workflow opens a pull request only. It never creates, amends, splits, or rewrites commits; use `atomic-commit` when commit preparation is needed. Repository instructions and canonical pull-request template win over this guidance. Do not assume a forge, branch name, ticket syntax, runtime, or command: discover them from the repository and its remotes. Do not invent verification, attribution, or review evidence.

## 1. Establish the target

Read repository instructions, forge metadata, the canonical pull-request template, remotes, default/protected branches, recent history, current branch/head, and status. For the default route, establish exactly one base/head range; record repository, forge, remote, base, head, and status. For `gitflow`, record one base/head range per twin after selecting its two bases. Stop on a dirty worktree, a protected or default branch as the working head, or an ambiguous target; do not draft or publish. A dirty worktree is a handoff to `atomic-commit` when appropriate.

**Complete when:** The default committed head and remote have one unambiguous base, or each Gitflow twin has its own recorded base/head, and the worktree is clean.

## 2. Reconstruct the change

Inspect the complete base/head diff, surrounding code, and history relevant to intent. In Gitflow, inspect the complete diff per twin and keep any base-specific differences visible. Account for every changed file and classify each by reviewer impact: visible UI; frontend state, routing, or data flow; API or backend; data, migration, index, or compatibility; configuration, dependency, or rollout; and tests, docs, or refactoring. Derive the title and ticket only from reliable repository or branch evidence; otherwise use a concise Conventional Commit-style title without guessing.

**Complete when:** Every changed file and material reviewer concern is represented in the default draft, or in the appropriate Gitflow twin brief, or explicitly marked immaterial.

## 3. Verify the changed behavior

Select the smallest repository-defined checks covering the highest-risk behavior, then run them. Preserve exact commands and observed outcomes; unrun checks remain unverified. For Gitflow, record one verification result per twin (a shared check may be reused only when its evidence applies to both). For visible UI, require a screenshot or recording of the changed behavior. If evidence cannot be captured, state that it is missing, do not invent verification, and ask the user to supply or unblock it; missing UI evidence pauses PR creation. End that response with a direct request for the user to supply or unblock the screenshot or recording, rather than merely reporting the blocker. For backend/API changes, include concrete executed tests or reproducible request evidence when useful.

**Complete when:** The default record truthfully covers the highest-risk behavior, or each Gitflow twin has its own truthful verification result, or the blocker that prevents creation is stated.

## 4. Draft the reviewer brief

Use the repository template as the schema, filling every applicable section and removing comments, examples, placeholders, and unused optional sections. Never output an illustrative or fill-in-the-blank draft: if facts are unavailable, say the draft is incomplete rather than showing placeholders. Read the [fallback PR body](references/fallback-pr-body.md) only when no canonical template exists. Explain customer/user value, implementation, rationale, risks, compatibility, data/infra effects, and exact verification. Use Mermaid only for at least three material interactions or transitions. For Gitflow, draft one reviewer brief per twin and keep each brief tied to its own range and evidence. Do not include runtime-specific attribution.

**Complete when:** A cold reviewer can understand value, load-bearing changes, impact, and observed verification without reconstructing the diff.

## 5. Preview and create

Preview all of the forge, base, title, body, verification, and missing evidence. For Gitflow, preview each twin's forge, base, title, body, verification, and missing evidence separately. Invocation authorizes normal non-force push and forge creation after preview; no second approval gate is requested. If verification or required UI evidence is missing, report it and stop before any push or creation. Stop on push or creation failure and report the exact failure; never force push or perform destructive recovery.

Without the exact `gitflow` argument, produce one portable PR by default: use the discovered forge tooling for the established range, then return its stable URL.

With the exact `gitflow` argument, route only the Zapsign/Bitbucket Gitflow case. Read the [Gitflow facts](references/gitflow-facts.md), the repository's `CLAUDE.md`, and `bt --llm` before relying on volatile branch or PR details. Identify `{TICKET}` from reliable branch or repository evidence. Check `git branch -a` and `bt pr list` first for idempotent existing-resource reuse; reuse an existing twin or PR and mark a leg complete when its base already contains the ticket commits.

When neither twin contains the ticket commits, discover the completed source patchset from the current branch, identify whether its base is `main` or `homolog`, and bootstrap the matching source twin from that patchset with a normal non-force push. Then mirror it with `bt pick` to the other twin; never open an empty PR.

For an existing pushed twin, use reuse, fast-forward, or cherry-pick only; never refresh or rewrite it. If its history diverges from the expected base, divergence stops the flow: report exact branch/PR facts and never rewrite or force-push the branch.

- Fast-forward `main` and `homolog` with `git pull --ff-only` before branching. Create a missing `{TICKET}-prd` from `main` targeting `main`, and a missing `{TICKET}-hml` from `homolog` targeting `homolog`; never branch `-hml` from `main`.
- Carry cherry-picked equivalent patches with `bt pick show`, then `bt pick run` (PRD to HML) or `bt pick run -r` (HML to PRD); after a conflict use `bt pick continue`. Never merge between bases or merge `main`/`homolog` into a twin. Use normal pushes only: no force push.
- Push each needed twin, then create two informative PRs (one per twin) with the exact `bt pr create --no-push --ai --close-source-branch` invocation, reusing any existing PR instead of duplicating it.
- Use terminal pipeline monitoring for both PRs: list runs with `bt run list --branch <branch>` and watch each with `bt run watch <id>`. For a red pipeline, diagnose with `bt run view <id> --log-failed`, preserve and report its exact failed evidence, and make an implementation/commit handoff. This PR-only workflow does not modify code or create commits, push, or mirror a fix; stop and report the required handoff. Return both PR IDs and the terminal pipeline result for each twin; creation alone is not completion.

**Complete when:** The preview is recorded, the selected mode's one PR or two twin PRs are created or safely reused, and (for `gitflow`) both pipelines have terminal results; otherwise the exact blocker or failure is returned.

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
| Publishing before preview | Preview forge, base, title, body, verification, and missing evidence, then use the invocation-authorized normal non-force push and forge creation. |
| Leaving generic placeholders in the body | Fill or remove every applicable template section with concise, reviewer-oriented evidence. |
