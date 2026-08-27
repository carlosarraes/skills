---
name: check-data
description: Use when planning and loading schema-aware local database rows for branch or ticket QA, with optional plan-only mode.
---

# Check data

Plan, seed, and verify realistic local rows for the current branch in one uninterrupted invocation. Accept the optional `plan-only` argument and an optional platform (`linear` by default, or `jira`). The default writes or reuses a plan, seeds it, and verifies counts; `plan-only` writes the plan only and makes no database or API mutation. This skill plans fixtures, not QA test cases (`/qa-ticket`).

## Step 1: Discover context

Run independent discovery reads in parallel where possible:

1. Parse arguments. Recognize `plan-only`; use the other argument as platform. Unknown platforms fall back to `linear` and are noted in the report.
2. Run `git rev-parse --abbrev-ref HEAD`. Extract the first case-insensitive `[a-zA-Z]{2,5}-\d+` match and uppercase it; if absent, use the diff only. Fetch ticket title, description, and acceptance criteria with `linear issue view <ID>` or `jira issue view <ID> --plain`. A missing CLI or failed fetch is non-fatal; record no ticket context and continue.
3. Read `git diff develop...HEAD --stat` and the full diff. It is authoritative for touched tables/collections and their roles. If there is no diff, report "no changes relative to develop" and stop without writing a plan.
4. Discover the local store in this order: compose files, running containers, environment/framework configuration, then the project’s own DB CLI. Capture engine, host/port, database, user, container, and project CLI. Never copy passwords, tokens, connection URLs, or raw command output into a report.
5. Find project seed/factory scripts (`Makefile`, package scripts, management commands, `db/seeds*`, Prisma or top-level seed scripts), inspect their coverage, and read each in-scope schema/model/migration. Record types, nullability, lengths, defaults, `UNIQUE`/`CHECK` constraints, and FK targets. Query current counts through the project path or the most direct safe DB path. If no DB is reachable, write the plan with the connection marked "not discovered", report seeding/verification as blocked, and do not silently switch to an unapproved service.

Map direct tables/collections and FK dependencies. Use roles from the diff: CRUD, read/display, lookup/reference, and filter/search. Add every parent needed for a valid dependent row, even when the parent is not changed.

## Step 2: Plan data

For every in-scope table/collection, propose roughly 3–5 happy rows and 2–4 rows in each other bucket, adjusted for small lookup tables. Every row has a concrete shape (field-level values) and one-sentence **Why**. Use FK placeholders only when insertion order determines the key. The four buckets are:

- **Happy path.** Typical valid values with enough variation for ordinary lists and filters.
- **Edge cases.** Schema and product boundaries: max-length and one-character text, empty optional values, numeric/date limits, and soft limits.
- **Error paths.** Insertable imperfect state: soft deletion, legacy enum, stale timestamps, missing optional references, or half-migrated nullable fields.
- **Stupid paths.** Insertable Unicode/RTL/emoji, HTML or script-shaped text, near-limit strings, whitespace/control characters, and SQL-injection-shaped strings.

Respect the discovered schema for every row: do not plan rejected FK/PK/type values, violate `NOT NULL` or `CHECK`, or turn this plan into test assertions. For a non-null field that would otherwise be empty, use a valid sentinel and explain it.

Write the report under `.notes/` when it exists, otherwise `ai_docs/`, in `<branch-name>/`. Use `data-plan.md` as the current plan. If it already exists, inspect its recorded branch/head/schema: current-plan reuse is allowed; otherwise preserve the old plan and write a new `data-plan-<short-sha>.md` candidate (reuse an existing candidate for that SHA). There is no overwrite-approval prompt. Include ticket/platform/date, redacted DB connection, tables with before counts and roles, all four row buckets, insertion notes, and warnings. Raw credentials never appear in reports.

If `plan-only` was passed, stop immediately after writing or reusing the plan: report the path and **no database mutation**, and do not enter Steps 3–4. Otherwise continue from this plan in the same invocation without a second skill or confirmation.

## Step 3: Seed data

Read the selected plan, including hand edits. The insertion preference is project seed/factory → ORM/REPL → direct DB/collection → API; fall through only when the preceding mechanism cannot cover the planned rows. Do not use an API merely because a local DB is temporarily unreachable. For Mongo, use collections and document references; for multiple stores, keep a connection block per store.

Walk dependency order with **FK parents first**, then each table’s buckets in happy → edge → error → stupid order. Capture generated keys and resolve placeholders from rows inserted or found in this run.

Make re-runs idempotent in this order:

1. Prefer a **natural-key match** (email, SKU code, or unique display name) and skip an existing row.
2. Otherwise use a **seed tag**, such as `seed:<branch>-<short-sha>`, in an available metadata/notes field and skip matching tagged rows.
3. If neither is possible, document that no idempotency key exists and let existing `UNIQUE` constraints prevent collisions; never delete or replace user data.

Record `before` counts before inserts. Insert one row at a time, continue after a row error, and perform per-row failure accounting as inserted, skipped, or failed with a concise reason. Defer FK failures and retry them once after the first pass; surface remaining failures rather than hiding them. Keep secrets out of commands, captured output, and reports.

## Step 4: Verify counts

Re-query counts after insertion and compare each table’s expected increase with the observed result. The verification ledger must contain **before/inserted/skipped/failed/after** for every table, for example:

```text
| Table | Before | Inserted | Skipped | Failed | After |
| users |     12 |        0 |       2 |      0 |    12 |
```

Explain every skip and failure, and flag an after-count mismatch or unexplained external change as a verification limitation. It is not success. A clean re-run should show zero new inserts and natural-key/seed-tag skips.

## Step 5: Report

Update the selected markdown plan with the seed mechanism, idempotency choice, row ledger, verification ledger, failures, and limitations. Print a concise handoff containing the local path, platform/ticket context, tables and counts, what was inserted/skipped/failed, and whether verification matched. For `plan-only`, explicitly say seeding and verification were not run and that no database/API mutation occurred. Never print raw credentials.

Handle these cases explicitly: missing ticket context (use the diff), unknown platform (use Linear and note it), no DB (blocked seed/verify), stale or hand-edited plans (preserve and version), schema drift (skip affected rows and recommend a fresh plan), unique conflicts (skip and explain), Mongo (collections/document references), and multiple DBs (separate connection blocks).
