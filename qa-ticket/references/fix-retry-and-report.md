# Fix, Retry, and Report

Read this file before diagnosing/remediating a failure and again before the final report.

## Diagnose before changing anything

Classify the observed problem:

- **Test bug:** route, payload, setup, or expected value is wrong. Correct only the test input/setup; do not list a production fix.
- **Code bug:** evidence contradicts intended behavior. Make the smallest fix in changed scope; do not refactor unrelated code.
- **Environment/data issue:** service, browser, auth, or fixture cannot support a sound conclusion. Mark `SKIP/INCONCLUSIVE`, do not silently patch the environment, and give a recovery next step.

Backend diagnosis uses captured status/body and focused logs when necessary. Frontend diagnosis uses fresh snapshot/screenshot/API evidence. Never invent retry evidence.

## Attempt bound

Allow **at most three total attempts per test**. Attempt 1 is the initial execution—not “three retries.” Between failed attempts, record diagnosis and what changed.

1. Execute attempt 1.
2. Diagnose failure.
3. Apply a minimal test correction or changed-scope code fix.
4. Wait for backend reload as the project requires. For frontend changes, **frontend edit → HMR wait → network-idle wait → fresh refs → retry** is one indivisible transition after every edit, including the first.
5. Execute attempt 2; repeat diagnosis/remediation once if needed.
6. Execute attempt 3, the final permitted attempt.
7. If still failing, stop. Record FAILED and the complete attempt history. Never run attempt 4.

Unavailable prerequisites before execution produce zero attempts and `SKIP/INCONCLUSIVE`. Keep every fix and touched path in the run ledger. For frontend retries, record each edit, both waits, fresh-ref acquisition, and retry in that order. Both waits mean HMR and network idle.

Write one complete ledger row per frontend edit: `Edit: <file> | HMR: observed | network idle: observed | fresh refs: acquired | next attempt: <N>`. Audit every frontend edit ledger entry before retry and before reporting. A row missing any field is an incomplete and invalid trace; it must be corrected before retry or report. Never summarize several edits under one collective wait entry.

## Final report contract

The inline report contains:

- branch, ticket/platform, date, and internally consistent PASS/FAIL/SKIP counts;
- degraded-mode notes such as provider failure, diff-only scope, unavailable surface/browser/data, or one-surface applicability;
- **every planned test** with ID, surface, category, expected behavior, result, **every attempt**, and concise evidence;
- for each failure: expected, actual, root cause, complete attempt history, and a concrete **recovery next step**;
- every test-input correction, code fix, and **every changed file** (a test correction is not a production change);
- cleanup outcome and any remaining local data;
- an explicit verdict on whether the ticket's **acceptance criteria** are satisfied.

Keep successful notes short but evidence-bearing. Do not omit successful rows to shorten the report. A required failure or unexecuted case makes the overall acceptance verdict not satisfied or explicitly qualified—never unconditionally green. Separate verified product failures from environment limitations and provide a specific recovery next step for both unresolved product work and unavailable environment/data/browser setup.
