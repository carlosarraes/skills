---
name: orchestrate
description: Coordinate broad work through checkpointed skill/subagent/worktree workflows. Use when the user asks to orchestrate, coordinate, parallelize, use subagents, run a fleet, drive multiple tickets/PRs, watch CI/reviews, or execute/QA work across phases. Routes to existing focused skills when they fit, including prep-ticket, brainstorming, grilling, exec-ticket, qa-ticket, chaos-engineering, and pr-sweep.
---

# Orchestrate

Coordinate broad work without turning it into one giant unattended script. Keep one parent session as the orchestrator, delegate bounded work to the host harness's agents/jobs/tools, and stop at checkpoints before risky transitions.

## Core loop

1. **Classify the request.** Identify the mode, scope, inputs, risk, and whether a focused skill already owns the work.
   - Completion: mode and focused-skill routing are explicit.
2. **Map the fleet.** Break the work into independent streams, dependencies, one-writer boundaries, and validation gates.
   - Completion: every stream has an owner shape, isolation plan, and validation target.
3. **Choose models.** Use the scorecard below; cheaper models gather/build broadly, high-taste models judge product/API/UI/architecture.
   - Completion: each stream has a model class or escalation rule.
4. **Present the checkpoint plan.** Show phases, agents/jobs, worktrees, skills, stop conditions, and expected artifacts.
   - Completion: the user can approve, edit, or cancel before execution.
5. **Execute one checkpoint at a time.** Launch only the approved phase. Synthesize results before proceeding.
   - Completion: results are summarized with evidence, failures, and the next checkpoint.

Do not launch a large fleet, parallel implementation, push/merge/rebase, approval-invalidating commit, destructive local action, or product/security/architecture decision without a checkpoint.

## Modes

### `orchestrate`

Use for freeform coordination. Pick the smallest workflow that fits:

- If a focused skill clearly owns the request, invoke that skill instead of reimplementing it.
- If work can be split safely, propose a fleet with read-only scouts/reviewers first and one writer per worktree.
- If the task is too broad, decompose it into phases and ask for the first checkpoint.

Completion: a checkpointed plan is approved or the request is routed to a focused skill.

### `orchestrate exec`

Turn one or more tickets into implemented work.

Single ticket:
1. Run `prep-ticket`.
2. Use `brainstorming` and/or `grilling` to settle the approach.
3. Checkpoint on the implementation plan.
4. Run `exec-ticket`.

Multiple tickets:
1. Run `prep-ticket` in parallel, one agent/job per ticket.
2. Synthesize dependency/conflict map: shared files, sequencing, blockers, likely merge conflicts.
3. Use `brainstorming`/`grilling` per ticket or for the shared plan.
4. Checkpoint before implementation.
5. Run `exec-ticket` in parallel only for independent tickets, each in an isolated worktree.
6. Checkpoint before merge/rebase/PR actions.

`exec-ticket` owns TDD, YAGNI, and implementation discipline. Orchestrate owns sequencing, isolation, and checkpoints.

Completion: each ticket has either an implemented/verified worktree or a blocked/deferred reason.

### `orchestrate exec-auto`

Same as `orchestrate exec`, but accept the recommended answer in brainstorming/grilling by default.

Stop and ask instead of auto-accepting when the decision changes product behavior, security posture, data model, public API, user-facing copy/design, deployment risk, or cross-ticket sequencing.

Completion: recommended choices are applied only where risk is low and explicit stop conditions did not trigger.

### `orchestrate qa`

Drive acceptance and resilience testing.

1. If local data is likely missing, run `check-data`, checkpoint, then `seed-data` if approved.
2. Run `qa-ticket` for happy/error/edge acceptance testing.
3. Run `chaos-engineering` for resilience testing.
4. For failures, use one writer to fix, then rerun the focused failing checks.
5. Checkpoint before destructive local actions or broad fix loops.

Use `agent-browser` when browser/runtime/UI verification is needed and available; `qa-ticket` and `chaos-engineering` already know when to use browser-style testing, so do not duplicate their internals.

Completion: QA and chaos results are summarized with pass/fail evidence and remaining risks.

### `orchestrate watch`

A smarter PR sweep loop for CI, review threads, and bot/human feedback.

1. Discover target PRs and classify each as done, waiting, needs-fix, or checkpoint-gated.
2. Use read-only agents/jobs for inspection and one writer per PR/worktree for fixes.
3. Protect approvals: checkpoint before avoidable commits to approved PRs.
4. Prefer focused `pr-sweep` behavior for GitHub mechanics; add orchestration when multiple PRs, model routing, or cross-PR dependencies matter.
5. Loop only at user-approved cadence; report each iteration's PR states and next actions.

Completion: all watched PRs are clean/mergeable, waiting on external actors, or explicitly handed back.

## Model scorecard

Use a 1-5 score. Higher cost means more expensive. These are defaults, not limits.

| model | cost | intelligence | taste | default use |
|---|---:|---:|---:|---|
| GPT-5.5 | 3 | 4 | 3 | bulk implementation, investigation, review, migrations, data/code analysis |
| Sonnet | 3 | 3 | 4 | wrapper agents, routine review, tool bridging, medium-complexity work |
| Opus | 4 | 4 | 4 | architecture/API/design review, higher-confidence critique |
| Fable | 5 | 5 | 5 | parent orchestration, product calls, hardest architecture, final review |

Rules:
- Never use Haiku for real work when these options exist.
- Use cheaper models for broad exploration and mechanical work.
- Use high-taste models for product judgment, UI/API design, architecture, and final review.
- If a cheaper model's output is weak, escalate without asking. Judge output quality, not the price tag.
- Checkpoint before risky actions regardless of model.

## Access paths

Models are separate from access paths.

| access path | use |
|---|---|
| Host subagents/workflows/jobs | Native delegation and fanout in the current harness: Claude Code Task/workflows, Pi subagents/chains, Codex jobs, or equivalent. |
| Codex CLI headless | Run GPT-5.5 via `codex exec` with self-contained prompts for code/review/research/data work. |
| agent-browser | Browser/runtime/UI verification, screenshots, and interaction debugging when available. |
| Worktrees | Isolation for parallel implementation or risky edits. |

When using `codex exec`, provide a self-contained prompt with repository path, goal, constraints, files to inspect, allowed write policy, validation command, timeout expectations, and output format. Label wrapper agents/jobs with a `gpt-5.5:` prefix so the fleet view reveals the real worker model.

## Fleet rules

- **One writer.** Only one agent/job writes to a given worktree at a time. Parallel writers require isolated worktrees.
- **Fresh reviewers.** Reviewers/scouts should inspect actual files/diffs from fresh context, not rely on parent summaries.
- **Artifacts over vibes.** Ask delegates for file paths, commands run, failures, diffs, and concise verdicts.
- **Bounded prompts.** Give each delegate one role, one goal, constraints, validation, and output shape.
- **Escalate on ambiguity.** Ask the user when a decision is product/security/architecture-sensitive or when streams conflict.
- **Use workflows where deterministic.** Fanout, review, verification, and polling are good workflow targets. Checkpoint-driven product work is not one giant workflow.

## Checkpoint template

Before an execution phase, report:

```markdown
## Orchestration checkpoint: <phase>

Goal: <what this phase should accomplish>
Streams:
- <stream>: <agent/job/skill>, <model>, <worktree/isolation>, <writes?>, <validation>

Risk gates:
- <merge/push/approval/destructive/product/security risk or "none">

Expected artifacts:
- <reports, branches, PRs, test output>

Proceed? yes / edit / cancel
```

Completion: the user approves, edits, or cancels; do not treat silence as approval.

## Final report

End every orchestration run with:

- Mode and scope handled
- Agents/jobs/skills used
- Worktrees/branches/PRs touched
- Validation evidence
- Decisions made at checkpoints
- Remaining risks or blocked items
- Recommended next command or skill
