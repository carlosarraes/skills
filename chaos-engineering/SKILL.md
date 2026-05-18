---
name: chaos-engineering
description: "Stress-tests the current branch by injecting application-level chaos — malformed input, auth bypass, races, dependency failure, resource abuse, frontend chaos, time skew — then auto-fixes resilience violations test-first with one conventional commit per finding. Extracts ticket from branch (Linear default, Jira via 'jira' arg), reads diff + ticket, dispatches 7 parallel chaos-design agents, writes `.notes/<branch>/chaos-plan.md` (or `ai_docs/<branch>/chaos-plan.md`), then prompts the user to confirm before running backend (curl) and frontend (agent-browser) attacks. Trigger on 'chaos engineering', 'chaos test', 'break this feature', 'stress test', 'find weaknesses', 'resilience test', 'fuzz this endpoint', 'what could break this', 'attack my endpoint', '/chaos-engineering'. Localhost only — refuses staging/prod. Pairs with /qa-ticket: qa-ticket proves it works, chaos-engineering proves it survives."
---

# Chaos Engineering

Break the current branch on purpose. Inject malformed input, auth bypass attempts, race conditions, dependency failure, resource abuse, frontend chaos, and time skew at whatever the diff touched — then prove the feature degrades gracefully, rejects safely, or fix it test-first if it doesn't.

This skill is the application-level counterpart to infrastructure chaos (kill pods, sever network, blow up CPU). Those tools target the platform; this one targets *the code on your branch*. The blast radius is naturally contained because the experiments only hit endpoints and components the diff actually changed.

## Why this exists

QA proves the happy path. Linters prove the syntax. Type checkers prove the shapes. None of them prove the feature survives:

- a JSON body that's 1MB of nested arrays
- a user with the wrong role hitting an admin endpoint by guessing the URL
- two browser tabs submitting the same form 50ms apart
- an upstream API returning 500 for 30 seconds
- a paste-bomb of 10k characters into a text input
- a clock that's six hours ahead

Vibe-coded features routinely ship without considering any of these. The bug surfaces in prod, the postmortem blames "edge cases", and the regression is one engineer-week later. This skill front-loads that engineer-week into the branch — and turns every failure into a permanent regression test.

> **Cross-skill pairing**: run `/qa-ticket` first to prove the feature works at all. Then run this skill to prove it survives abuse. If your local DB needs varied data first, run `/check-data` then `/seed-data`. If after this run you want a senior-engineer audit of code quality, run `/clean-up`.

## When to use this skill

Trigger when:
- The branch is feature-complete and passes `/qa-ticket`, but hasn't been hardened
- The change touches input validation, auth, persistence, an external integration, or a hot path
- The user explicitly says "chaos", "break this", "resilience", "find weaknesses", "stress test", "fuzz this"
- A reviewer (human or AI) flagged "what about <weird input>?" and you want a systematic answer

Do NOT use for:
- A branch that doesn't even pass the happy path — run `/qa-ticket` first
- One-line typo fixes or pure refactors (nothing to attack)
- Production / staging environments — this skill operates against localhost only and refuses otherwise
- Pure infrastructure chaos (kill pods, sever network) — that's what Litmus, Chaos Mesh, or Gremlin are for; this skill targets your code, not your platform

## Prerequisites

Discover the project's local dev setup before designing experiments. Check `CLAUDE.md`, `README.md`, `docker-compose.yml`, `package.json` scripts, or `Makefile` for:

- **Backend URL** (e.g., `localhost:8000`)
- **Frontend URL** (e.g., `localhost:3000`)
- **Auth setup** — test-mode bypass, mock JWT, or real credentials
- **Platform CLI** — `linear` or `jira` authenticated
- **Test runner** — `pytest` / `jest` / `vitest` / etc. (needed for the TDD fix loop)

Health-check the running app (parallel Bash):
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:<BACKEND_PORT>/docs
curl -s -o /dev/null -w "%{http_code}" http://localhost:<FRONTEND_PORT>
```

If backend isn't reachable, the chaos plan can still be designed (static analysis of the diff), but execution is skipped for that surface — note it in the report. Same for frontend.

> **Hard rule — localhost only**: If the discovered backend or frontend URL resolves to anything other than `localhost`, `127.0.0.1`, or `0.0.0.0`, **refuse to execute experiments**. Print the URL, explain the guardrail, and ask the user to point the project at a local instance. This is non-negotiable — chaos against shared environments corrupts other people's work and against production is a resignation letter.

---

## Step 1: Gather context

Run 1a-1e in parallel — they're independent.

### 1a. Parse optional platform argument

If the user passed an argument (e.g., `/chaos-engineering jira`), set **platform** to that value. Supported: `linear` (default), `jira`. Unrecognized → default to `linear` and note it in the report.

### 1b. Extract ticket ID from branch

```bash
git rev-parse --abbrev-ref HEAD
```

Match the pattern `[a-zA-Z]{2,5}-\d+` **case-insensitively** and uppercase the result (e.g., `feature/abc-123-add-sku-validation` → `ABC-123`). If no match, ask the user: "Could not extract a ticket ID from branch `<name>`. What's the ticket ID (e.g., ABC-123)?" — the ticket framing helps the chaos agents target their attacks.

### 1c. Fetch ticket details

**Linear** (default):
```bash
linear issue view <TICKET-ID>
```

**Jira**:
```bash
jira issue view <TICKET-ID> --plain
```

Extract: title, description, labels, priority, acceptance criteria. The ticket clarifies *what the feature is supposed to do* — which tells the chaos agents what "resilient" looks like (e.g., "rejects with 400" vs "queues for retry" vs "returns cached value").

### 1d. Fetch code diff against develop

```bash
git diff develop...HEAD --stat
git diff develop...HEAD
```

The diff is the authoritative scope. Parse it for:
- **Endpoints**: route handlers, new `@app.post(...)` / `app.use(...)` / `router.add_route(...)`
- **Schemas / models**: Pydantic models, SQLAlchemy / Prisma / Django models, validators
- **Auth code**: permission checks, role guards, token validation
- **External calls**: `httpx`, `fetch`, `axios`, SDK clients
- **Persistence**: new DB writes, transactions, queue publishes
- **Frontend**: React components, forms, mutations, state hooks

These five buckets map directly onto the chaos categories below.

### 1e. Discover dev environment

In parallel with the above, run:
```bash
test -d .notes && echo "use .notes" || echo "use ai_docs"
ls docker-compose*.yml 2>/dev/null
find . -maxdepth 2 -name pyproject.toml -o -name package.json | head -5
```

Capture: output dir, test runner, framework. The output dir decision (Step 4) and the test runner (Step 7) depend on this.

---

## Step 2: Define steady-state hypotheses

Before designing chaos, write the resilience contract. For each changed endpoint / component, fill in:

> **If [chaos], then the feature should [behavior].**

Examples:
- *If the request body has a 10MB payload, then the endpoint should reject with 413 within 100ms, not OOM.*
- *If a regular user POSTs to `/admin/sku/{id}`, then the server should return 403 and log the attempt, not 200.*
- *If two requests create the same idempotency key concurrently, then exactly one row is persisted, the other returns the same response.*
- *If the upstream `inventory` service returns 500, then the order endpoint should return a friendly "try again" message, not propagate a stack trace.*

These hypotheses are the **pass/fail oracle** for every experiment. If you can't write a steady-state for a changed endpoint, ask the user — chaos without an oracle is just vandalism.

---

## Step 3: Dispatch 7 parallel chaos-design agents

Spawn **seven agents in parallel** in a single message (all `Explore` subagent_type, all independent). Each agent gets:
- the diff (`git diff develop...HEAD`)
- the ticket summary
- the steady-state hypotheses from Step 2
- a category-specific focus (one of the 7 below)

Each agent must return 3-8 experiments with: **ID, hypothesis, experiment (concrete payload / interaction), expected resilience behavior, severity (P0/P1/P2/P3), blast radius**. Cap each agent at ~500 words so the synthesis stays scannable.

The 7 categories are deliberately broad so coverage is consistent across runs. Even if the diff "obviously" doesn't touch auth, run the auth agent — it'll either return "no experiments, no auth code in scope" (cheap) or surprise you with an IDOR you missed (expensive to learn in prod).

| # | Category | Concrete attack seeds |
|---|----------|------------------------|
| 1 | **Input / injection** | Malformed JSON (`{"a": }`, trailing comma, unbalanced brace), type confusion (string for int, array for object), oversized strings (10k, 100k, 1M chars), missing required fields, unicode (emoji, ZWJ sequences, RTL/LTR mixing, combining diacritics), HTML / script tags (`<script>`, `<img src=x onerror=...>`), SQL / NoSQL injection patterns (`'; DROP TABLE`, `{"$ne": null}`), prompt injection (if an LLM is downstream), deeply nested JSON (200 levels), prototype pollution (`{"__proto__": {"isAdmin": true}}`), negative numbers where positive expected, leading / trailing whitespace, null bytes |
| 2 | **Auth / security** | Missing token, expired token, tampered token (flip one signature byte), wrong-algorithm token (`alg: none`), role escalation (regular user hits admin route), IDOR (swap `/users/<my-id>` → `/users/<other-id>`), tampered URL params, CSRF (cross-origin POST with browser cookies), replay attack (resend identical request with same nonce), secrets in error responses (assert `password`/`secret`/`api_key` not in body or logs), timing-side-channel on login (compare timing for valid-user-wrong-pw vs unknown-user) |
| 3 | **State / race** | Concurrent double-submit (two requests, same body, 0ms apart), idempotency-key reuse (same key, different body — must reject), out-of-order webhook delivery (event 3 before event 2), partial-transaction failure (kill connection mid-write — DB consistency check after), stale-read after write (read immediately after write — must return the new value or proper error), conflicting updates / lost update (two ETag-less PATCHes — last-write must be detected or merged), retry storm (10 retries in 1s — circuit breaker must engage) |
| 4 | **Dependency** | Upstream timeout (mock the dependency to hang 30s), upstream 5xx (mock to return 500), malformed response (HTML when JSON expected), partial success (200 with `{"status": "partial"}`), slow trickle (return one byte every 5s, Slowloris-shaped), DNS failure (point client at a black hole), HTTP 429 from third-party, circuit-breaker behavior (verify it opens after N failures and closes after recovery) |
| 5 | **Resource** | Payload bomb (1MB JSON, deeply nested arrays), zip-bomb on upload endpoints (1KB zip that expands to 1GB), rate-limit storm (100 req/s — assert 429 or queue, not crash), N+1 amplification (one request that triggers fan-out queries — check DB query log), unbounded list pagination (`?limit=999999` — must clamp), memory exhaustion via large `?limit=` or `?ids=<huge list>`, recursive query (cyclic graph traversal) |
| 6 | **Frontend / UX** | Rapid clicks (10 clicks in 1s on the same button — must dedupe), double submits, paste-bombs (10k chars into a text input — UI must not freeze), network throttle (slow-3G — UI must show loading + not double-submit), mid-flight cancellation (navigate away during submit — no orphan record, no error toast on cancelled-by-user), lost websocket reconnection, browser back during multi-step flow, keyboard-only nav (Tab + Enter only — every interactive must be reachable), copy-paste with rich formatting (Word-styled text into a `<textarea>` — must strip), drag-drop of non-image into an image field |
| 7 | **Time** | Clock skew (set request `Date` header ±6h), far-future timestamps (`year 3000`), far-past (`year 1899`), DST transition timestamps (the missing hour), timezone confusion (UTC vs server-local vs user-local — verify rendering is consistent), leap-day (Feb 29), token expiry boundary (request 1s before and 1s after expiry) |

---

## Step 4: Synthesize the chaos plan

Aggregate the 7 agent reports into a single `chaos-plan.md`.

**Output path**:
- If `.notes/` exists at repo root → `.notes/<branch-name>/chaos-plan.md`
- Else → `ai_docs/<branch-name>/chaos-plan.md` (create `ai_docs/` if missing)

`mkdir -p` the branch subdirectory first. Branches with slashes (e.g., `feature/abc-123-foo`) create nested directories — that's intentional.

If `chaos-plan.md` already exists for this branch, **ask the user** before overwriting; offer to show a diff.

### chaos-plan.md template

```markdown
# Chaos Plan: <branch-name>

- **Ticket**: <TICKET-ID> — <title>   *(or "no ticket")*
- **Platform**: linear | jira
- **Date**: <YYYY-MM-DD>
- **Output dir**: ai_docs | .notes
- **Backend URL**: <localhost:port>   *(or "not reachable — execution skipped")*
- **Frontend URL**: <localhost:port>   *(or "not reachable — execution skipped")*
- **Test runner**: pytest | jest | vitest | go test | ...

## Steady-state hypotheses
- `<Endpoint or Component>`: <resilience contract>
- ...

## Experiments

### 1. Input / injection
| ID | Hypothesis | Experiment | Expected resilience | Severity | Blast radius |
|----|------------|------------|---------------------|----------|--------------|
| I1 | ... | `curl -X POST ... -d '<payload>'` | 400 with `{"error": "..."}`, no stack trace | P1 | none |

### 2. Auth / security
| ID | ... |

(repeat per category — skip categories the agents found no experiments for, but say so explicitly: "Category 7 (time) — no time-sensitive code in scope, skipped.")

## Notes & warnings
- **Data-mutating experiments**: <list the IDs> — these write rows. Re-run `/seed-data` after if you want a clean state.
- **Auth bypass**: experiments that use forged tokens — list creds / cookies used so they're easy to revoke.
- **Destructive risk**: experiments that could leave the DB in a weird state — flag them so the user can choose to skip.
```

Print the plan inline (or its summary if huge) so the user sees what's about to happen.

---

## Step 5: Confirm with the user

After printing the plan, prompt:

> **Ready to execute. Pick one:**
> - `all` — run every experiment
> - `<IDs>` — comma-separated (e.g., `I1, A2, S3`), only run these
> - `<category>` — run a single category (e.g., `auth`, `input`)
> - `abort` — write the plan to disk, run nothing

Block until the user answers. **No experiment runs without confirmation** — this is non-negotiable because chaos against a running app is a one-way door for some categories (rate-limit storms, payload bombs, write-skew races).

If the user picks `abort`, write the plan to disk and stop here. They can come back later with `/chaos-engineering` and the existing plan will be detected and offered for re-execution.

---

## Step 6: Execute the selected experiments

Run experiments **sequentially**, not in parallel — parallel execution makes attribution impossible when something blows up.

### Backend experiments

Use `curl` with the crafted payload. Capture status, response body, response time:

```bash
curl -i -X POST "http://localhost:<PORT>/<path>" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '<payload>' \
  -w "\n---\nstatus=%{http_code} time=%{time_total}s\n"
```

After each backend experiment, also check:
- **Server logs** (tail the dev server output) — assert no stack traces leaked into the response, no secrets logged at INFO level
- **DB state** — for mutation experiments, run a `SELECT` to verify the side effect matches the hypothesis (e.g., "exactly one row created" for idempotency tests)

### Frontend experiments

If the diff touched the frontend, **load the `agent-browser` skill** first (don't try to use it without loading the skill — it has a specific API).

For each frontend experiment:
1. Navigate to the relevant page
2. Take a snapshot to confirm initial state
3. Inject the chaos (rapid clicks, paste, throttle)
4. Wait for network: `agent-browser wait --load networkidle`
5. Re-snapshot — **every click or form submit invalidates the previous snapshot**
6. Compare observed UI behavior against hypothesis

For unresponsive Radix-UI components (a known issue with the agent-browser click handler), fall back to JS eval:
```bash
agent-browser eval --js "document.querySelector('<selector>').click()"
agent-browser wait --load networkidle
agent-browser snapshot
```

### Classify each outcome

Tag every experiment as:
- **resilient** — observed behavior matches the steady-state hypothesis. No fix needed.
- **violated** — observed behavior breaks the hypothesis. Goes to Step 7 for fixing.
- **inconclusive** — couldn't reach a clear answer (test infra issue, env mismatch). Document and skip — don't pretend it passed.

---

## Step 7: Auto-fix violations test-first

For every **violated** experiment, run a strict TDD cycle. This mirrors `/clean-up` Step 5 and exists for the same reason: a fix without a regression test is a fix that gets re-broken in three months.

### 7a. Triage severity

- **[P0] and [P1]** — always fix. These are the reason this skill exists (data corruption, auth bypass, crash on input).
- **[P2] and [P3]** — fix if straightforward. Skip if the fix would balloon scope into a separate refactor (e.g., "the entire pagination layer needs a rewrite").

If you skip a finding, say so explicitly in the final report — never silently drop one.

### 7b. RED → GREEN → Commit (per finding)

1. **RED** — Write a regression test that asserts the resilient behavior. Run it. Confirm it fails for the right reason (e.g., the endpoint currently returns 500 instead of 400). If the test passes immediately, you wrote the wrong test.
2. **GREEN** — Apply the minimal code change to make the test pass. No drive-by refactors, no "while I'm here" cleanup. If you notice something else broken, file it as a follow-up and keep moving.
3. **Verify** — Run the relevant test file or directory. Confirm no regressions in adjacent tests.
4. **Commit** — One focused commit per finding (see 7c).

Max 3 attempts per finding. After 3 failed fixes, mark **FAILED** in the report with what was tried and why it didn't work — the user decides next steps.

### 7c. Commit discipline

Each commit must:
- Be staged by explicit path: `git add backend/src/handlers/order.py backend/tests/test_order.py`. **Never** `git add -A` or `git add .`.
- Use **Conventional Commits**: `<type>(<scope>): <description> (TICKET-ID)` where type is `fix` for resilience bugs, `feat` if adding a new validator, `test` only if it's purely a missing test for already-correct code.
- Have a one-line subject (per the global `CLAUDE.md` commit rule).
- Explain the **WHY** in the body — the reviewer should understand the bug class (e.g., "IDOR — endpoint didn't check ownership; users could fetch others' rows by guessing IDs") without re-reading the diff.
- Pass pre-commit hooks. If hooks reformat files, re-stage and commit again — **never** `--no-verify`.
- Never commit `CHANGELOG.md` or `TASKS.md` (global rule).

One commit per finding lets `git bisect` work, lets the human re-review commit-by-commit, and lets you revert a single fix without losing the others.

---

## Step 8: Final report

Print the report **inline in chat** (do not write it to disk — the chaos-plan.md is the durable artifact; the report is the conversation summary).

```markdown
# Chaos Report: <TICKET-ID> — <ticket title>
**Branch**: <branch>
**Date**: <YYYY-MM-DD>
**Resilient**: X resilient, Y violated, Z inconclusive (of N total)

## Per-experiment outcomes
| ID | Category | Hypothesis | Observed | Outcome | Severity |
|----|----------|------------|----------|---------|----------|
| I1 | input | reject 10MB body with 413 | 200 OK, 8s | **VIOLATED** | P0 |
| A1 | auth | reject regular user on /admin | 403 in 12ms | RESILIENT | — |
| ... | | | | | |

## Fixes applied
| Finding | File:line | Change | Commit |
|---------|-----------|--------|--------|
| I1 — 10MB body OOM | `backend/src/middleware.py:42` | Added `MAX_BODY_SIZE=1MB` check before parse | `<sha>` |
| ... | | | |

## Skipped / failed
- **F2** — flagged as P3 (unbounded `?limit=`), would require rewriting pagination — filed as follow-up.
- **S1** — race condition fix failed after 3 attempts: writing a deterministic test for the concurrent path needs a transaction-isolation harness this project doesn't have yet.

## Feature resilience: **yes / partial / no**
<2-3 sentences: what now survives, what still doesn't, what the user should do next>

## Hand-back
- Review commits: `git log --oneline develop..HEAD`
- Re-run a single experiment: `/chaos-engineering` then pick its ID
- Push when ready (this skill does not push or open PRs)
```

Show **every** experiment, not just violations. The "resilient" rows are evidence the feature is hardened against that class of attack — that's the deliverable.

---

## Step 9: Hand back

After printing the report:

- **Do not** push, force-push, open a PR, merge, or amend commits.
- Tell the user the resolved branch is unchanged from their perspective (still checked out), plus N new commits.
- Suggest `/clean-up` next if any of the fixes felt large or if the cumulative diff might benefit from a senior pass.
- Suggest `/seed-data` if any data-mutating experiments left the local DB in a weird state.

---

## Guardrails (hard rules)

These exist because chaos engineering is, by nature, willing to break things. The guardrails define what it must *not* break.

1. **Localhost only**. Refuse to execute experiments if the discovered backend or frontend URL resolves to anything other than `localhost`, `127.0.0.1`, or `0.0.0.0`. Staging and production are explicitly off-limits — they have users and shared state, and one rate-limit storm can take a team's morning.
2. **Plan-before-execute is non-negotiable**. The user must confirm in Step 5 before any chaos hits the running app. The plan-only path (`abort`) is always available.
3. **One commit per finding**, conventional commits, body explains WHY, never `--no-verify`, never `git add -A`.
4. **Never push**. This skill produces local commits only. The user decides when to push.
5. **No CHANGELOG.md / TASKS.md commits** (global `CLAUDE.md` rule).
6. **Data-mutating experiments are flagged in the plan** so the user knows the local DB may need re-seeding via `/seed-data`.
7. **No test = no execution of fixes**. If the project has zero tests for the changed surface, warn the user, offer to run `/qa-ticket` first to establish a smoke baseline, and stop. Auto-fixing without a test is exactly the anti-pattern this skill is fighting.
8. **Auth bypass attempts use throwaway tokens / test users**, never real production credentials. If the only auth path is "real user", flag in the report and skip those experiments rather than risk leaving forged tokens lying around.

---

## Pairing with other skills

| Skill | When |
|-------|------|
| `/qa-ticket` | Run **before** this skill to prove the happy path works. Chaos against a broken feature is just noise. |
| `/check-data` + `/seed-data` | Run **before** if local DB lacks varied data (filters, edge cases, FK refs). |
| `/clean-up` | Run **after** if the chaos fixes felt heavy and the cumulative diff deserves a senior-engineer pass. |
| `/atomic-commit` | If you ended Step 7 with several findings squashed into one commit by accident, use this to split them. |
| `/be-pr` / `/frontend-pr` | When the user is satisfied with the chaos report, they can run these to open the PR. This skill never does. |

The mental model: `/qa-ticket` proves the feature works; this skill proves the feature *survives*. Use both — they catch different bugs.
