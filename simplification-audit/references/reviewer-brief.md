# Bounded reviewer brief

## Assignment

Review one exact subsystem identified by the coordinator: its stated ownership
boundary, implementation, public interfaces, major call sites, and tests. Keep
the review inside that boundary. You may identify cross-subsystem evidence, but
return it as evidence only; the coordinator owns any follow-up boundary. Return
at most two opportunities or `skip`.

## Look for

- Scattered booleans or nullable fields that permit invalid combinations and
  belong in a state machine or discriminated union.
- Repeated assumptions about object shape that need a shared typed model.
- Duplicated branching a small map, registry, reducer, or command model would
  remove.
- Unclear state or behavior ownership that a small module boundary would
  clarify.
- Repeated scans, transformations, or lookups that a suitable collection or
  index would materially simplify.
- Lifecycle, concurrency, or async state whose representation permits stale or
  contradictory state.

## Materiality gate

Recommend only a change that reduces invalid states, duplicated decisions,
repeated work, lifecycle contradictions, or unclear ownership. Prefer boring
local code when it is already clear. Reject style-only consistency, hypothetical
extension, minor line-count reduction, and abstractions that only relocate
branching.

## Return schema

Return `skip` when no candidate clears the materiality gate. For each of at
most two opportunities, provide:

1. **Verdict:** `recommend` or `skip`.
2. **Evidence:** exact file-and-line references.
3. **Current complexity or invalid states.**
4. **Proposed representation** and why it is simpler.
5. **Smallest credible implementation scope,** including affected files and interfaces.
6. **Regression risks** and migration concerns.
7. **Validation:** existing and additional validation required.
8. **Confidence:** high, medium, or low.
