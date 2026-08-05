---
name: chaos-engineering
description: Use when a locally running, feature-complete branch needs resilience, abuse, fuzz, race, dependency-failure, or adversarial testing after its happy path works.
---

# Chaos Engineering

Break the changed application behavior on purpose, compare it with an explicit resilience oracle, and repair proven violations test-first. This is branch-local application chaos, not infrastructure chaos. `/qa-ticket` should already prove the happy path.

## Operating contract

Run these phases in order:

1. Gather ticket, diff, project environment, auth/test setup, URLs, and health in parallel.
2. Define a steady-state “if chaos, then behavior” oracle for every changed surface. Ask the user when any oracle is missing.
3. Launch exactly seven independent category-design agents in a single parallel batch.
4. Synthesize the durable branch plan, resolving any existing-plan overwrite gate.
5. Display the plan and block until the user selects `all`, IDs, one category, or `abort`.
6. Execute only the selection, strictly sequentially, and classify each result `resilient`, `violated`, or `inconclusive`.
7. TDD-fix eligible violations independently, with bounded attempts and one local commit per successful finding.
8. Print the complete final report and hand back the checked-out local branch.

Do not skip or reorder a gate because the user asked to “run everything,” supplied an earlier authorization, called an environment disposable, or requested publication.

## Preview and simulation mode

Use dry-run mode only when the request contains the exact marker `SIMULATION ONLY`, or explicitly makes the **entire run** a simulated, preview-only, or read-only trace with **no execution or mutation**. Then describe the exact actions, decision pauses, planned agent batch, artifact path/content, evidence, commits, and hand-back that a real run would produce, but call no networks, agents, browser, ticket provider, or git mutation and write no plan or report file.

`Read-only` by itself is not a mode switch. Requests such as “execute only read-only experiments” still execute the safe selected experiments through every normal gate. A normal run still creates the durable plan before selection; simulation does not weaken or replace that contract.

## Hard gates visible at entry

### Loopback only

Every attacked application and dependency must resolve exclusively to `localhost`, `127.0.0.1`, or `0.0.0.0`. A local UI wired to a nonlocal API is nonlocal. Print each offending URL, refuse all execution, and ask for a loopback instance. User authorization never waives this rule. Do not infer runtime outcomes or remediate from static speculation.

An unreachable loopback surface may still receive static discovery and design. Mark it unreachable, skip experiments for that surface, and never fabricate a runtime conclusion.

### Oracle before design or attack

Ticket intent frames resilience and the diff is authoritative attack scope. Every changed endpoint/component needs an observable steady-state hypothesis before category design. If the intended status, body, state, or degradation behavior is unclear, ask; do not invent a pass condition.

### Plan and selection before execution

The seven-agent plan must be synthesized, persisted, and displayed before execution. An existing plan needs explicit overwrite confirmation and a diff offer. No experiment starts until the post-plan selection. `abort` preserves the plan and runs nothing.

### Evidence before outcomes

Only evidence matching the oracle is `resilient`. Infrastructure, dependency-injection, environment, or observation ambiguity is `inconclusive`, never a pass. Selected experiments never overlap.

## Phase router

### 1. Discover local scope

Read [local discovery](references/local-discovery.md) in full **before discovery or health-check work**. Follow its platform fallback, ticket extraction, diff scope, output-dir precedence, URL resolution, credential rules, reachability fallback, and no-diff/no-ticket decisions.

If any attacked surface/dependency is nonlocal, stop at the loopback gate. Otherwise gather independent context concurrently. Do not start category design until each changed surface has an oracle.

### 2. Define oracles and design experiments

Read [chaos categories](references/chaos-categories.md) in full **before defining the final steady-state set or before dispatch**. Launch exactly seven agents in one single parallel batch, one for each fixed category, even when a category appears irrelevant. Prompts are independent and do not expose the team, count, or synthesis.

Wait for all seven results. A category with nothing in scope remains explicit as skipped; never silently remove a category.

### 3. Create and show the plan

Read [chaos plan](references/chaos-plan.md) in full **before writing, replacing, or displaying a plan**. Preserve `.notes`/`ai_docs` precedence and slash-containing branch nesting. If the plan exists, stop for overwrite consent and offer a diff; do not treat the request to run as overwrite permission.

Normal mode writes the plan, then displays it or a viable full summary with risks and the selection prompt. Simulation mode describes the would-be path and content but does not write.

### 4. Parse selection and execute

Read [execution](references/execution.md) in full **before parsing the selection or before executing any experiment**. Accept only `all`, explicit IDs, a category, or `abort`. Initial user language from before the displayed plan is not the selection.

Execute selected experiments strictly sequentially. Capture response, log, DB, and browser evidence as applicable before classifying one experiment and beginning the next. Unselected and unreachable experiments are skipped and remain reportable.

### 5. Remediate violations

Read [TDD remediation](references/tdd-remediation.md) in full **before fixing any `violated` result**. P0/P1 findings require an attempt; P2/P3 are fixed only when straightforward. No valid same-finding RED test means no production edit.

After valid RED, make the smallest change and verify it. Allow at most three total attempts per finding. Each successful finding gets exactly one local commit; failed or out-of-scope findings get none.

### 6. Report and hand back

Read [hand-back](references/handback.md) in full **before reporting or hand-back**. The inline final report includes every planned experiment as selected, resilient, fixed, failed, inconclusive, unreachable, or otherwise skipped; it never hides an unsuccessful or unselected case.

Derive the overall verdict from the combined evidence, not the worst row alone: mixed meaningful success with a material unresolved result is `partial`; use `no` only when no meaningful resilience remains or the core feature is broadly unsafe.

Leave the branch checked out and local. Recommend reseeding when experiments mutated data and `/clean-up` when fixes were substantial.

## Never rules

- Never attack staging, production, shared services, or a local surface that calls them.
- Never execute before the displayed plan and explicit post-plan selection.
- Never run selected experiments in parallel.
- Never call ambiguous evidence resilient.
- Never use real production credentials; use throwaway/test users and tokens or skip/report the auth experiment.
- Never edit production code before a valid failing regression test for that same finding.
- Never bypass hooks. Never use `git add .`. Never use `git add -A`, and never commit `CHANGELOG.md`/`TASKS.md`.
- Never combine findings into one commit, split one successful finding across commits, or exceed three remediation attempts.
- Never push or force-push. Never open a PR, never merge, never amend, and never rewrite published history. Local commits are the publication boundary.

## Related skills

- Run `/qa-ticket` first when the happy path is not proven.
- Run `/check-data` then `/seed-data` first when realistic local rows are missing.
- Run `/clean-up` afterward when the fixes expanded the cumulative diff.
