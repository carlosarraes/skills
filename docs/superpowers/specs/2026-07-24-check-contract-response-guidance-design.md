# Check-contract Response Guidance Design

## Context

Immutable evaluation iteration 4 failed the acceptance gate at 0/9 treatment
samples. Eight treatment runs submitted a code judgment and received
`RESPONSE_INVALID`; three treatment runs timed out. Replaying the recorded
judgments through `validate_code_judgment` identifies the same first failure
in every submitted response: fidelity-family clauses cite evidence namespaces
that the validator forbids.

The runtime owns this rule, but its code packet and the skill do not expose the
allowed evidence IDs per fidelity clause. The model therefore receives a
closed validator without the complete contract needed to satisfy it.

Iteration 4 and its rejected review remain immutable.

## Decision

Keep the validator strict. Make the runtime communicate the existing rule
directly:

1. Each code packet includes a runtime-owned mapping from every fidelity
   clause ID to the exact issued evidence IDs that clause may cite.
2. The skill tells the agent to select fidelity evidence only from that
   per-clause mapping.
3. The skill asks for one short sentence per reason so the required complete
   judgment remains bounded.

The mapping is derived from the same rule pack and issued evidence inventory
used by validation. The skill does not duplicate namespace prefixes or policy
logic.

## Data flow

```text
rule pack + issued evidence
        ↓
runtime derives allowed IDs per fidelity clause
        ↓
code packet exposes the closed mapping
        ↓
agent writes a concise judgment using only mapped IDs
        ↓
existing strict validator accepts or rejects
```

Non-fidelity clauses, path assessments, YAGNI/reuse items, and deviations keep
their existing issued-evidence contract.

## Safety and scope

- Do not relax evidence namespace ownership.
- Do not permit retries or change single-use response semantics.
- Do not change aggregation, verdicts, routes, publication, or compound
  closure.
- Do not mutate contracts, ledgers, implementation, or iteration-4 evidence.
- Keep `check-contract/SKILL.md` at or below 500 words.
- Reuse existing rule-pack and packet-building logic; add no general schema
  framework.

## Tests

Test-first coverage must reproduce the recorded failure shape:

- a model-like fidelity judgment that uses an otherwise issued
  `source:CAPTURE-1` is rejected before the fix guidance exists;
- the emitted packet maps each fidelity clause to only its allowed issued IDs;
- the skill requires using that mapping and concise one-sentence reasons;
- existing validator, runtime, skill, change-contract, and exec-ticket suites
  remain green.

## Evaluation gate

After independent code review:

1. Run one isolated Claude treatment canary on a representative fixture.
2. Require it to reach `AuditComplete` with only the active report changed.
3. If the canary fails, preserve it and return to diagnosis without starting
   the full benchmark.
4. If it passes, run fresh immutable iteration 5 with nine treatment and nine
   freshly paired controls under the existing no-retry, 360-second,
   maximum-concurrency-two protocol.
5. Installation remains blocked until iteration 5 achieves 9/9 treatment full
   samples and an independent reviewer returns `ACCEPT`.
