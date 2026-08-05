# Bounded TDD Remediation

Read this file before editing code for a violated experiment.

## Eligibility

- **P0/P1:** always attempt a tested minimal repair.
- **P2/P3:** repair only when straightforward within the changed surface. Skip/file when it requires architectural or multi-module scope expansion.
- **No test, no auto-fix:** when the changed surface has no usable test harness, warn, offer `/qa-ticket` for a baseline, report the violation, and stop without production edits.

Skipped work is explicit in the final report; never silently drop a finding.

## Same-finding RED first

For each eligible finding independently:

1. Write a regression test that asserts its steady-state behavior.
2. Run it and prove RED for the intended reason. A test that passes immediately is invalid: correct and rerun it before any production edit. A setup/syntax failure is not valid RED.
3. Only after valid RED, make the smallest production change and rerun the finding test plus relevant adjacent tests.
4. Stop when GREEN and verified; no drive-by refactor.

Each production-change/verification cycle after valid RED is one remediation attempt. Permit **at most three total attempts per finding**, not an initial attempt plus three retries. After the third failure, stop, make no commit, and report every attempt and why it failed.

## One successful finding, one local commit

After GREEN and adjacent verification:

- stage source and regression tests by **explicit path** only;
- use one commit for this finding and no other finding;
- use `<type>(<scope>): <description> (TICKET-ID)` with `fix`, `feat`, or test-only `test` as appropriate;
- keep a one-line subject and explain the bug class and **why** in the body;
- run normal hooks. If a hook reformats a path, re-stage that explicit path and retry normally.

Exactly one local commit per successful finding. A failed, inconclusive, resilient, unreachable, or out-of-scope finding gets no commit. Never amend or combine work for convenience.

## Forbidden operations

- Never `git add .`, `git add -A`, broad-stage, or stage unrelated user work.
- Never `--no-verify`, disable hooks, skip required adjacent verification, or treat a passing-before-fix test as RED.
- Never stage or commit `CHANGELOG.md` or `TASKS.md`.
- Never push, force-push, open a PR, merge, or amend.

The router-qualified whole-run simulation mode narrates test-validity decisions, attempt count, explicit paths, would-be subjects/bodies, hook behavior, and commit mapping, but performs no edits, tests, staging, commits, or publication. “Read-only” attached only to experiments does not activate it.
