---
name: qa-ticket
description: Use when the current ticket branch needs executable acceptance or smoke testing against a local backend or frontend, including fix-and-retry.
---

# QA Ticket

Run evidence-backed acceptance QA for the current ticket branch against its local development surfaces. This workflow may make minimal, changed-scope repairs during bounded retries; it does not infer runtime success from code.

## Operating contract

Run these phases in order:

1. Preflight project-local setup, auth, URLs, platform, ticket, `develop...HEAD` diff, and surface health.
2. Build a targeted plan from ticket requirements **plus** changed functional code.
3. Print the complete plan before any functional test.
4. Execute reachable backend and frontend cases with authoritative routes and fresh evidence.
5. Diagnose each failure before any bounded retry or fix.
6. Print a truthful final report containing every planned test and all evidence.

Do not weaken the coverage floor, evidence requirements, or report because the user asks for speed, happy paths only, or a green verdict.

## Whole-run simulation

Enable simulation only for exact marker `SIMULATION ONLY` or when the user makes the **entire run** a no-execution preview. After loading, issue **no repository commands, no provider commands, no service commands, no browser commands, and no mutations**; do not inspect files, read references, call agents, or invent observations. Use supplied facts only for the would-be trace, plan, evidence classifications, limitations, and report; label actions and fixes simulated.

For each frontend edit, emit this simulation ledger: `Edit: <file> | HMR: would wait | network idle: would wait | fresh refs: would acquire | next attempt: <N>`. Classify supplied outcomes separately; never claim a simulated wait, ref acquisition, edit, or retry was observed or occurred.

Normal runs are unchanged: smoke/read-only/no-edit requests are not simulation; they still perform discovery and executable QA.

## Hard gates

### Preflight and context before testing

Read [QA context](references/qa-context.md) in full **before preflight** and **before gathering** ticket/diff context. In normal runs, verify project URLs/auth/setup and both surface health before tests. Resolve platform (`linear` default; `jira` accepted), normalize the ticket ID, and gather `develop...HEAD` independently.

If the ticket provider fails, continue disclosed **diff-only** planning; never invent requirements. Missing ticket context stays diff-only without prompting; affected evidence is `SKIP/INCONCLUSIVE`. An unavailable surface keeps planned cases `SKIP/INCONCLUSIVE`, never PASS. If no diff, report and stop.

### Complete targeted plan before execution

Read [test planning](references/test-plan.md) in full **before drafting** and **before printing** the plan. Scope comes from the ticket plus diff and excludes unchanged modules, infrastructure, generated/style churn, and unrelated authentication.

Every case has ID, surface, description, concrete steps, and expected result; its category is exactly `happy-path`, `error`, or `edge-case`. Include every changed endpoint success path. When CRUD applies, preserve **create → read → update → list → delete → verify delete**. Include all validator boundaries on both sides, missing/wrong fields, permission, not-found, conflict, and every relevant frontend error/state/special-input case. Document a changed rate limit but do not stress-hit it merely to prove the annotation. User pressure cannot remove required coverage. Print the complete plan grouped by surface/category before any functional test.

For missing or unavailable data, print in the plan:
Fixture setup: /check-data (default: plan → seed → verify)
Use the alternate only with evidence:
Fixture setup: not needed — <evidence>
A single /check-data invocation owns all three phases; never express them as multiple skills or commands. Keep the complete backend and frontend happy-path/error/edge-case coverage floor enumerated even when a surface is unavailable; mark each such result as `SKIP/INCONCLUSIVE`.

### Evidence, not intention

Discover routes authoritatively; a user guess never overrides OpenAPI, router, source, or diff evidence.

- Backend PASS requires the expected **status and expected response content**. Use unique data, capture returned IDs, keep lifecycle order, and clean up.
- Frontend PASS requires the browser skill, safe dev auth, current refs, waits, and a **fresh post-action** snapshot/URL/visible-state assertion. DOM-changing actions invalidate old refs. Stale text and code inspection are not evidence.
- An unavailable service, data fixture, provider, or browser is `SKIP/INCONCLUSIVE`, never PASS. A spinner caused by failed data is not an empty-state pass.

Read [backend QA](references/backend-qa.md) in full **before any backend** discovery/test and [frontend QA](references/frontend-qa.md) in full **before any frontend** discovery, browser setup, or test. Skip unaffected surfaces with an explicit report note.

### Bounded diagnosis and remediation

Read [fix, retry, and report](references/fix-retry-and-report.md) in full **before diagnosing** the first failure or changing test/application code. Classify the cause as test bug, code bug, or environment/data issue before remediation.

Allow **at most three total attempts per test**: the initial attempt counts. Diagnose between attempts. Keep fixes minimal and within changed functional scope. A test-input correction is not a production fix. Treat **frontend edit → HMR wait → network-idle wait → fresh refs → retry** as one indivisible ordered transition after every edit, including the first.

Write one complete ledger row per frontend edit: `Edit: <file> | HMR: observed | network idle: observed | fresh refs: acquired | next attempt: <N>`. Audit every frontend edit ledger entry before retry and before reporting. A row missing any field is an incomplete and invalid trace; it must be corrected before retry or report. After attempt three, retain FAILED with its full history; never take a fourth attempt or turn failure into green prose.

### Complete report and truthful verdict

Read [fix, retry, and report](references/fix-retry-and-report.md) again **before the final report**. Include every planned test, result, attempts, expected/actual evidence, skip or failure, diagnosis, fix, and every changed file. For missing or unavailable data, repeat in the final report:
Fixture setup: /check-data (default: plan → seed → verify)
Repeat the alternate only with evidence:
Fixture setup: not needed — <evidence>
Preserve the complete backend and frontend happy-path/error/edge-case coverage floor in the report even when a surface is unavailable, marking each such result as `SKIP/INCONCLUSIVE`. Keep PASS notes concise; preserve complete unsuccessful histories.

State whether the acceptance criteria are satisfied. Any required FAIL or unexecuted case prevents an unqualified satisfied verdict. Separate product failures from environment limitations and provide a concrete recovery next step for each unresolved product or environment issue.

### Pre-output audit

Before returning, including simulation, audit both artifacts: the printed plan and final report. Ensure each has the Fixture setup field; use not-needed only with evidence. Never emit `/seed-data` as an executable command; rewrite any `/seed-data` occurrence because that entrypoint is deleted.

## Never rules

- Never run a functional test before local preflight/context and the printed plan.
- Never test a guessed route when authoritative evidence exists.
- Never call status-only backend evidence, stale browser evidence, code inspection, intention, or an unavailable dependency PASS.
- Never silently drop required happy, error, or edge coverage.
- Never exceed three total attempts for one test.
- Never retry or report while a frontend-edit ledger row is incomplete.
- Never expand a fix into unchanged modules or unrelated refactoring.
- Never omit a planned row, attempt, failure, skip, fix, changed file, limitation, or acceptance caveat from the final report.

## Related skills

- Use `/check-data` once (default plan → seed → verify) for missing rows; this skill tests behavior, not fixture provisioning.
- Load `agent-browser` before frontend execution.
