# Selection, Execution, and Outcomes

Read this file before parsing the post-plan choice or executing experiments.

## Selection gate

Accept `all`, explicit IDs, one category, or `abort`. Validate IDs/category against the displayed plan and clarify invalid/ambiguous input. `abort` preserves the normal durable plan and stops all execution. Initial “run all” language from before plan display is not authorization.

In the router-qualified whole-run simulation mode, return the ordered would-be trace and decisions, but make no experiment, network, browser, DB, log, edit, commit, or other mutation call. No experiment runs merely because the prompt supplies assumed outcomes. A request for read-only experiments still follows normal selection and execution.

## Sequential attribution

Run only selected experiments, **strictly sequentially**. Experiment N+1 may start only after N has all applicable response/log/DB/browser evidence and a classification. Never overlap experiment windows.

For an unreachable loopback surface, mark its experiments skipped/unreachable. For a nonlocal target or dependency, refuse the run entirely under the router's hard gate.

### Backend evidence

For each backend experiment capture separately:

- HTTP status;
- response body;
- response time;
- relevant server logs, including absence/presence of stack traces and secrets;
- DB state or queue/event state for mutations and race/idempotency claims.

Status alone is insufficient when the oracle names content, logs, time, or state. Use unique fixture data and clean up where the plan permits; retain contamination/reseed evidence.

### Frontend evidence

Load the `agent-browser` skill before browser actions. For each case:

1. navigate and snapshot initial state;
2. perform the one planned chaos interaction;
3. wait for relevant network/UI settling;
4. re-snapshot and compare with the oracle.

Every click, submit, navigation, or other DOM-changing action invalidates prior element references and snapshots. Re-snapshot before the next interaction. If an ordinary click on a Radix-style control does not transition state, a scoped JS click may be used, followed by wait and snapshot; record the fallback.

## Outcome taxonomy

- **resilient:** all evidence required by the steady-state oracle matches.
- **violated:** reliable evidence contradicts the oracle; route to remediation.
- **inconclusive:** infrastructure, dependency injection, environment, missing observation, or fixture ambiguity prevents a sound comparison.

Inconclusive is never resilient. A dependency-failure stub that cannot prove the request reached the dependency is inconclusive. A concurrent one-row claim requires DB evidence plus the responses. Record expected and observed evidence for every selected result. Retain unselected plan experiments as skipped in the final ledger.
