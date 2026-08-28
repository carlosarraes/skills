# Review rubric

Apply only relevant lenses. Trace a concrete path before raising a finding.

## Correctness and operations

- Boundary values, empty input, errors, encoding, stale state, and concurrency.
- Repeat or resume an operation. It should reconcile to the intended state
  instead of depending on debris from the prior attempt.
- Give one owner exclusive or serialized access to shared mutable state.
- Verify real output or state rather than trusting a summary, cache, dry-run
  label, or process liveness.

## Boundaries, types, and domain

- Validate external data once at the boundary and keep internal paths typed.
- Make illegal domain states hard to represent. Casts, optionality, and loose
  objects need a concrete reason.
- Keep orchestration, domain policy, persistence, and transport concerns in
  their canonical owners.
- Judge interfaces from their callers. A seam should remove complexity for
  more than one real consumer.

## Structure and migration

- Prefer deleting branches, flags, wrappers, and compatibility paths over
  rearranging them.
- When the repository controls all callers, migrate them and delete the legacy
  API in the same change.
- Ask how the design would look if the requirement had existed from the start.
  Flag bolted-on special cases only when a cleaner integrated shape is concrete.
- Convert repeated review lessons into a type, test, lint, helper, or runtime
  invariant when that structure prevents recurrence.

## Reader cost and scope

- Minimize facts a caller must remember, mixed abstraction levels, and
  indirection that hides simple data flow.
- Subtract unused options and speculative flexibility before adding machinery.
- Build reusable automation only after repeated mechanical work or measured
  leverage justifies its maintenance cost.
- Review the intended outcome. Do not reward activity, broad rewrites, or
  architecture unrelated to the stated change.

## Security

- Trace untrusted input to SQL, shell, evaluation, HTML, filesystem, or network
  sinks.
- Check authentication, authorization, secret handling, and time-of-check to
  time-of-use gaps touched by the scope.
