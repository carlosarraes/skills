---
name: interrogate
description: Use only when explicitly invoked for an adversarial multi-reviewer challenge of a diff, branch, pull request, design, or selected code.
disable-model-invocation: true
---

# Interrogate

Challenge code through independent reviewers, then make one pragmatic lead
judgment. Invocation authorizes a read-only review, not code changes. Keep the
reviewed work byte-for-byte unchanged and never apply findings automatically.

## 1. Resolve scope and intent

Use explicit files, a diff, a PR, or the current feature-branch delta. Resolve
the real base from PR metadata when available; otherwise use the repository's
default branch merge-base. Include surrounding types and call sites needed to
judge reachable behavior without dumping unrelated code into every prompt.

State one paragraph describing what the work is meant to achieve. Derive it
from the request, ticket, PR body, commits, tests, and code. Mark any inference.
Proceed with a reasonable read-only assumption when uncertainty only affects
review emphasis. Stop only when two materially different intents would produce
opposite verdicts.

## 2. Build one reviewer packet

Read [the reviewer prompt](references/reviewer-prompt.md) and
[the review rubric](references/rubric.md). Fill the packet with the same intent,
scope, context, and rubric for every reviewer. Independent models supply the
variation; assigned personas would make the evidence incomparable.

## 3. Spawn independent reviewers portably

Inspect the current runtime's actual subagent interface, available slots, and
model allowlist. Use those declarations rather than copied client tool names,
configuration paths, or historical model slugs.

- Run at least two reviewers. Prefer three or four when slots and cost allow.
- Use different model families when the runtime and the user's routing request
  permit it. Set model and reasoning effort explicitly when the spawn interface
  supports them.
- When only one model family is permitted, run independent fresh-context
  reviewers on that model and label the result `independent, not model-diverse`.
- Launch reviewers concurrently up to the available slot limit. Run the rest
  sequentially when needed.
- Give every reviewer the identical packet and read-only authority.

If no subagent interface exists or fewer than two independent reviews can run,
return `blocked` with the missing capability. One self-review is not an
interrogation.

## 4. Synthesize and verify

Merge duplicate findings and record which reviewers raised each one. Agreement
increases signal but does not replace evidence. Trace every candidate through
reachable callers, types, tests, or real execution before placing it in `Act
on`. Treat a concrete single-reviewer correctness or security path more
seriously than consensus on style.

Read [the lead-judgment guide](references/lead-judgment.md). Classify every
finding as:

- **Act on:** A demonstrated correctness, security, or maintainability issue
  that should block the reviewed work.
- **Consider:** A real tradeoff whose benefit may not justify its cost now.
- **Noted:** Valid context with no current action.
- **Dismissed:** Wrong, unreachable, preference-only, duplicate, or based on
  missing context. Give the rejection reason so the user can override it.

Cap `Act on` at five. If more than five findings survive, group the common cause
or rerun the evidence check. A long list is usually unfiltered review noise.

## Output

Return:

1. **Intent** with disclosed assumptions.
2. **Reviewers** with runtime, model, reasoning effort, finding count, and an
   explicit model-diversity statement.
3. **Act on**, **Consider**, **Noted**, and **Dismissed**.
4. **Agreement map** showing consensus, lone findings, contradictions, and what
   the pattern means.
5. **Verification limits** naming any finding that could not reach executable
   or source-backed proof.

For each actionable finding include location, reachable path, evidence,
reviewers, and the smallest plausible correction. End without editing files.
