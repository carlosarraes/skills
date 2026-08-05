# Local Discovery and Scope

Read this file before repository, ticket, environment, auth, URL, or health discovery. Provider commands and project conventions are time-sensitive; prefer current repository docs/config over the examples.

## Parallel discovery

Gather independent inputs concurrently:

1. Read `CLAUDE.md`, `AGENTS.md`, `README.md`, compose files, `package.json`, `pyproject.toml`, and `Makefile` as available. Identify backend/frontend commands and URLs, test runner, test authentication, dependency endpoints, and the active integration base (historically `develop`).
2. Run `git rev-parse --abbrev-ref HEAD`. Extract `[A-Za-z]{2,5}-\d+` case-insensitively and uppercase it. If absent, ask for the ticket ID; do not invent one.
3. Parse an optional platform argument. `linear` is default and `jira` is supported. An unknown platform falls back to Linear and must be noted in the report. Fetch current ticket title, description, labels, priority, and acceptance criteria with the available authenticated provider CLI. A provider failure permits diff-only design but is reported.
4. Inspect `git diff <integration-base>...HEAD --stat` and the full diff. The ticket frames intent; the diff is the authoritative attack scope. Locate changed endpoints, schemas/validators, auth, external calls, transactions/writes/queues, and frontend forms/state. If no branch diff exists, report that there is nothing changed to attack and stop.
5. If `.notes/` exists at repository root, choose `.notes`; otherwise choose `ai_docs`. Record the test runner/framework and do not create anything yet.

## Resolve every attacked URL

Build an endpoint/dependency ledger: configured URL, resolved hostname, source configuration, reachability, and whether a reachable local surface calls another host. Execution is permitted only when every attacked application and dependency resolves to exactly `localhost`, `127.0.0.1`, or `0.0.0.0`.

- A local frontend that calls staging is nonlocal and blocks both browser and backend attacks.
- “Disposable,” explicit authorization, and read-only-looking requests do not waive the boundary.
- Print offending URLs, refuse execution, and ask the user to point every surface/dependency to loopback.
- Do not health-check or attack a known nonlocal target merely to prove it exists.

For configured loopback surfaces, health-check backend and frontend concurrently using the project's documented endpoints. Record HTTP status or connection failure rather than assuming a conventional `/docs` route.

An unreachable loopback surface does not cancel static design from ticket/diff evidence. Mark its plan metadata `not reachable — execution skipped`; never execute that surface or claim runtime resilience. A reachable surface may proceed only if its dependency ledger is also loopback-only.

## Credentials and testability

Identify the existing test harness before any remediation. Auth attacks use test-mode bypasses, mock JWTs, and throwaway test users/tokens only. When only real-user or production credentials exist, skip and report those experiments.

If the changed surface has zero usable tests, chaos observation may still be reported, but do not auto-fix: warn, offer `/qa-ticket` to establish a smoke baseline, and stop remediation.

## Simulation

In explicit simulation/preview mode, describe this discovery ledger and the health checks that would run, but call no provider, network, browser, git mutation, or agent tool and write no files.
