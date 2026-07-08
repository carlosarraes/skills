---
name: orchestrate
description: Coordinate broad work through checkpointed skill/subagent/worktree workflows. Use when the user asks to orchestrate, coordinate, parallelize, use subagents, run a fleet, drive multiple tickets/PRs, watch CI/reviews, or execute/QA work across phases. Routes to existing focused skills when they fit, including prep-ticket, brainstorming, grilling, exec-ticket, qa-ticket, chaos-engineering, and pr-sweep.
---

# Orchestrate

Coordinate broad work without turning it into one giant unattended script. One parent session orchestrates, bounded work goes to fresh-context delegates, and risky transitions stop at checkpoints.

## The conductor rule

The orchestrator conducts; it never picks up an instrument. Legwork — ticket research, code reading, diff inspection, implementation — belongs to delegates. The orchestrator classifies, sequences, synthesizes reports, and checkpoints.

This rule is load-bearing: once you inline-research a ticket yourself, the delegated step feels redundant and gets rationalized into "a lighter equivalent" — but your ad-hoc gather skips the focused skill's checklist (blocker sweep, in-flight-branch scan, reuse scan), and no fresh-context report exists to cite at the checkpoint. If you are running `gh`/`git`/ticket lookups beyond what classification needs, you have left the podium. **prep-ticket done inline is not prep-ticket done.**

## Router

1. **Classify.** Mode, scope, inputs, risk. If a focused skill owns the request outright (one ticket to prep → `prep-ticket`, one branch to QA → `qa-ticket`, PR mechanics → `pr-sweep`), invoke that skill and stop — orchestration adds nothing.
   - Completion: mode named, or the request handed to a focused skill.
2. **Enter the mode workflow.** Create one todo per numbered step of the mode. A step is complete only when its Completion line is satisfied — not when its spirit feels honored.
   - Completion: todos exist before any delegation or research starts.

## Running a skill inside an agent

When a mode step says "dispatch `<skill>`", spawn one general-purpose agent per unit of work with a prompt of this shape:

> Invoke the Skill tool: skill=`prep-ticket`, args=`MON-1234`. Follow the skill fully. Return its report verbatim as your final message.

If the harness's agents cannot invoke skills, point the agent at the file instead: "Read `<skills-dir>/prep-ticket/SKILL.md` and execute it for MON-1234."

Never paraphrase a skill into an agent prompt ("do prep-ticket-style research", "map the surface like prep would"). A paraphrase silently drops the skill's checklist — the steps that exist precisely because they get skipped under pressure. The skill runs, or the step is not done.

## Modes

### `orchestrate`

Freeform coordination. Pick the smallest workflow that fits:

1. If work can be split safely, propose a fleet: read-only scouts/reviewers first, one writer per worktree.
2. If the task is too broad, decompose into phases and checkpoint on the first.

Completion: a checkpointed plan is approved, or the request was routed to a focused skill at the Router.

### `orchestrate exec`

Turn one or more tickets into implemented work. `exec-ticket` owns TDD, YAGNI, and implementation discipline; orchestrate owns sequencing, isolation, and checkpoints.

Single ticket:

1. Dispatch `prep-ticket`.
   - Completion: the agent returned the skill's readiness report.
2. Settle the approach with `brainstorming` and/or `grilling` (pre-grilled rule below).
   - Completion: one approach recorded, with its source — grill verdict or locked decisions.
3. Checkpoint on the implementation plan, citing the readiness report.
   - Completion: user approved or edited.
4. Dispatch `exec-ticket`.
   - Completion: implemented and verified worktree, or a blocked reason.

Multiple tickets:

1. Dispatch `prep-ticket` in parallel, one agent per ticket.
   - Completion: one readiness report per ticket, each returned by a dispatched agent running the skill. Inline research by the orchestrator does not satisfy this step, however thorough.
2. Synthesize the dependency/conflict map from those reports: shared files, sequencing, blockers, likely merge conflicts.
   - Completion: every ticket pair has a verdict — independent, sequenced, or conflicting.
3. Settle the approach per ticket (or one shared plan) with `brainstorming`/`grilling`.
   - Completion: each ticket has one approach with its source — grill verdict or locked decisions.
4. Checkpoint before implementation, citing the readiness reports and the map.
   - Completion: user approved or edited.
5. Dispatch `exec-ticket` in parallel only for independent tickets, each in an isolated worktree; sequenced tickets run in dependency order.
   - Completion: every ticket has an implemented/verified worktree or a blocked/deferred reason.
6. Checkpoint before any merge/rebase/push/PR action.
   - Completion: user approved or edited.

**Pre-grilled rule:** a ticket carrying locked/grilled decisions collapses "settle the approach" to restating those decisions at the checkpoint — do not re-litigate them. prep-ticket never collapses: it is the blocker/conflict sweep, and a pre-grilled ticket still grows fresh blockers after grilling.

### `orchestrate exec-auto`

Same as `orchestrate exec`, but accept the recommended answer in brainstorming/grilling by default.

Stop and ask instead of auto-accepting when the decision changes product behavior, security posture, data model, public API, user-facing copy/design, deployment risk, or cross-ticket sequencing.

Completion: recommended choices applied only where risk is low and no stop condition triggered.

### `orchestrate qa`

Drive acceptance and resilience testing.

1. If local data is likely missing, run `check-data`, checkpoint, then `seed-data` if approved.
   - Completion: required data confirmed present or seeded.
2. Run `qa-ticket` for happy/error/edge acceptance testing.
   - Completion: acceptance results with pass/fail evidence per case.
3. Run `chaos-engineering` for resilience testing.
   - Completion: resilience results with pass/fail evidence.
4. For failures, use one writer to fix, then rerun the focused failing checks.
   - Completion: each failure is fixed-and-green or explicitly deferred with a reason.
5. Checkpoint before destructive local actions or broad fix loops.
   - Completion: user approved or edited.

`qa-ticket` and `chaos-engineering` already know when to use browser-style testing; do not duplicate their internals.

### `orchestrate watch`

A smarter PR sweep loop for CI, review threads, and bot/human feedback.

1. Discover target PRs and classify each as done, waiting, needs-fix, or checkpoint-gated.
   - Completion: every PR in scope has a classification.
2. Use read-only agents for inspection and one writer per PR/worktree for fixes.
3. Protect approvals: checkpoint before avoidable commits to approved PRs.
4. Prefer focused `pr-sweep` behavior for GitHub mechanics; add orchestration only when multiple PRs, model routing, or cross-PR dependencies matter.
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
| Host subagents/workflows/jobs | Native delegation and fanout in the current harness: Claude Code Task/workflows, Pi subagents/chains, Codex jobs, or equivalent. Skills run inside agents per "Running a skill inside an agent". |
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

## Checkpoints

Never launch a large fleet, parallel implementation, push/merge/rebase, approval-invalidating commit, destructive local action, or product/security/architecture decision without a checkpoint.

Before an execution phase, report:

```markdown
## Orchestration checkpoint: <phase>

Goal: <what this phase should accomplish>
Built on: <readiness reports, dependency map, or QA evidence this plan cites>
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
