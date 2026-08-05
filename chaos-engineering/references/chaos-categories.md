# Oracles and Seven-Category Design

Read this file before completing steady-state hypotheses or dispatching category designers.

## Steady-state oracle

For every changed endpoint/component, write: **If [chaos], then [observable resilient behavior].** Include the required status/body/time, UI state, logging, persistence, or dependency behavior needed for a verdict. Examples:

- If a body is 10 MB, reject with 413 before parsing without an OOM.
- If a regular user calls an admin route, return 403 and log the attempt without secrets.
- If equal idempotency keys arrive concurrently, persist exactly one row and return the same logical response.
- If inventory times out, return the agreed retryable response without a stack trace.

Ticket language and existing tests may supply an oracle. When they do not, ask the user before design; do not accept “500 is fine” or infer intention from an old plan.

## Exactly seven independent designers

Launch exactly seven design agents in a **single parallel batch**, one per category below. Every category runs even when apparently irrelevant. Each individual prompt contains only:

- ticket summary;
- authoritative branch diff/scope;
- completed steady-state hypotheses;
- that agent's one category focus;
- required output: 3–8 experiments, each with ID, hypothesis, concrete payload/interaction, expected resilience, P0/P1/P2/P3 severity, and blast radius;
- approximately 500 words maximum.

Agents are independent. Do not mention other agents, their count, a team, parallelism, aggregation, or later synthesis in any individual prompt. Do not give one result to another agent. Wait for the whole batch before synthesis. A designer may return “no experiment in scope,” which becomes an explicit skipped category.

In simulation, emit the seven planned prompt summaries as one batch trace without launching agents.

## Fixed categories and seeds

1. **Input / injection:** malformed/trailing JSON, missing/wrong/null fields, negative/boundary values, 10k/100k/1M strings, Unicode/RTL/combining text, HTML/script, SQL/NoSQL/prompt injection, null bytes, prototype pollution, and 200-level nesting.
2. **Auth / security:** missing/expired/tampered/wrong-algorithm tokens, role escalation, IDOR, parameter tampering, CSRF, replay, secret leakage, and login timing. Use throwaway test identity only.
3. **State / race:** concurrent double-submit, idempotency-key reuse, reordered webhooks, partial transactions, stale reads, conflicting updates, lost updates, and retry storms.
4. **Dependency:** timeout, 5xx, malformed/partial response, slow trickle, local DNS/failure stub, 429, and circuit-breaker open/recovery behavior. Dependency injection itself must remain loopback-only and observable.
5. **Resource:** payload/decompression bombs, rate storms, N+1 amplification, excessive pagination/IDs, memory pressure, and recursive traversal. Keep every concrete attack within safe local fixture bounds stated in the plan.
6. **Frontend / UX:** rapid clicks/double submit, paste bombs, slow network, mid-flight cancellation, lost websocket, browser back, keyboard-only interaction, rich paste, and wrong drag/drop type.
7. **Time:** clock skew, future/past timestamps, DST, UTC/local rendering, leap day, and expiry boundaries.

The diff limits which concrete experiments survive synthesis; it never reduces the exactly seven design calls.
