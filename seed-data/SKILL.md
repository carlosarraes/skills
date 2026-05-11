---
name: seed-data
description: "Reads the data-readiness plan written by `/check-data` and inserts the planned rows into the local database. Auto-detects the project's preferred insertion mechanism (existing seed scripts, ORM management commands, raw SQL, or HTTP POST) and picks the highest-fidelity one available. Use this skill whenever the user says 'seed data', 'seed the db', 'load test data', '/seed-data', 'seed-data', 'run the data plan', 'load fixtures from plan', 'insert test rows', 'load the plan', 'apply the plan', or wants to populate the local DB with the rows /check-data planned. Also trigger right after `/check-data` finishes and the user says something like 'load it', 'now seed', or 'apply it'. Requires `/check-data` to have run first — reads `ai_docs/<branch>/data-plan.md` or `.notes/<branch>/data-plan.md`. Does NOT generate test cases (use `/qa-ticket`) and does NOT plan data (use `/check-data`)."
---

# Seed Data

Read the data plan written by `/check-data` and insert the planned rows into the local database. Prefer the project's own seed/factory mechanisms when they exist; fall back to direct SQL or API only when nothing better is available.

## Why this exists

`/check-data` plans varied rows (happy / edge / error / stupid paths) so the feature can be tested under realistic conditions. This skill turns that plan into actual DB rows. Splitting plan from execution lets you review and edit the plan before anything writes to the DB, and gives one clean place to handle insertion mechanisms across projects.

## Step 1: Locate the plan

Look, in order, for:

1. `ai_docs/<branch-name>/data-plan.md`
2. `.notes/<branch-name>/data-plan.md`

Get the branch via `git rev-parse --abbrev-ref HEAD`. If neither exists, stop and tell the user to run `/check-data` first.

If the plan file's mtime is older than the current branch's HEAD commit (`git log -1 --format=%ct HEAD`), warn the user — the diff may have moved on and the plan could be stale. Offer to continue anyway or stop and re-run `/check-data`.

## Step 2: Parse the plan

Pull these blocks from the markdown:

- **`## DB Connection`** — engine, host, port, db, user, container, project CLI, existing seed mechanism.
- **`## Tables in scope`** — table → current row count, role, notes.
- **`## Suggested data: <table>`** sections — each contains four sub-headings (`### Happy path`, `### Edge cases`, `### Error paths`, `### Stupid paths`) and bullet rows of the form `` `{ ... }` — Why: ... ``.
- **`## Notes & warnings`** — FK ordering hints, constraints, idempotency strategy.

Be tolerant of hand edits — the section headers are the contract. Treat anything inside `### <bucket>` sections as rows the user wants inserted, even if they added, removed, or rewrote rows. Don't assume row count or shape exactly matches what `/check-data` originally wrote.

## Step 3: Choose the insertion mechanism

Try in this order. Move to the next only if the current one can't cover the plan.

### 3a. Project's seed/factory script

If the plan's "Existing seed mechanism" line points to one (e.g., `make seed`, `npm run seed`, `python manage.py loaddata fixtures/sample.yaml`, `rails db:seed`, `prisma db seed`):

- **Read the script first** — does it produce enough variety to cover the plan's four buckets? Most project seed scripts only cover happy-path rows.
- If yes, run it and stop.
- If no, run it for the rows it does cover (typically the happy path), then fall through to a lower mechanism for edge / error / stupid rows.

### 3b. Management command / language REPL

If the project has one (`python manage.py shell`, `rails runner`, `node -e`, `bun -e`, `mix run`):

- Build a small script that imports the project's models/ORM and creates rows directly.
- This bypasses HTTP/auth concerns and respects model-level validation, defaults, signals, and timestamps.
- Preferred for Django, Rails, Prisma, TypeORM, ActiveRecord-style projects.
- Stupid-path rows (with quotes, backslashes, SQL-injection shapes) are safe here — the ORM handles escaping.

### 3c. Direct SQL / collection insert

Using the DB connection from the plan, execute INSERTs directly:

```bash
# Postgres
docker exec <container> psql -U <user> -d <db> -f - <<'SQL'
INSERT INTO users (name, email, status) VALUES ('Alice', 'alice@example.com', 'active');
SQL

# MySQL
docker exec -i <container> mysql -u <user> -p<pass> <db> <<'SQL'
INSERT INTO users (name, email, status) VALUES ('Alice', 'alice@example.com', 'active');
SQL

# SQLite
sqlite3 <path/to/db.sqlite3> <<'SQL'
INSERT INTO users (name, email, status) VALUES ('Alice', 'alice@example.com', 'active');
SQL

# Mongo
docker exec <container> mongosh <db> --eval 'db.users.insertOne({ name: "Alice", email: "alice@example.com", status: "active" })'
```

Watch for **FK ordering** — insert dependency tables (`users`) before dependents (`orders`). The plan's "Notes & warnings" section should call this out; otherwise infer from FK references in the model definitions.

**Quoting stupid-path rows in raw SQL** is fragile — strings with single quotes, backslashes, and `--` need careful escaping. Prefer heredocs (`<<'SQL'` with single-quoted delimiter to disable shell expansion) and use dollar-quoting in Postgres for values with single quotes:

```sql
INSERT INTO skus (name) VALUES ($$<script>alert(1)</script>$$);
INSERT INTO skus (name) VALUES ($$'; DROP TABLE skus; --$$);
```

If quoting gets hairy for a particular row, drop into 3b (management command) for that row — the ORM handles it cleanly.

### 3d. HTTP POST to project's own API

Last resort, when no DB/CLI/ORM access works (e.g., the user is on a hosted dev env without `docker exec`). POST each row through the project's create endpoints.

Limitations to flag in the chat summary:
- Can't seed soft-deleted rows (no API to set `deleted_at`).
- Can't set internal-only fields (created_by audit, system flags).
- Subject to API-level validation, which may reject some stupid-path rows that would otherwise be valid at the DB layer.

## Step 4: Insert rows

Walk the plan in this order: for each table (FK parents first), for each bucket (happy → edge → error → stupid), insert each row.

For each row:
- Insert it.
- Capture the returned PK so subsequent rows referencing it (e.g., `<categories.id widgets>` in the plan) can resolve.
- On failure, **record but continue** — don't abort the whole run. Common failure modes:

| Failure | Likely cause | Action |
|---------|--------------|--------|
| UNIQUE constraint violation | Row already exists (re-run, natural-key collision) | Skip with a note |
| NOT NULL violation | Plan omitted a required column | Skip with a note; suggest re-running `/check-data` |
| FK violation | Parent row failed earlier, or ordering wrong | Defer and retry once after the rest of the pass |
| CHECK violation | Stupid-path row violated a constraint the plan missed | Skip with a note |
| Type mismatch | Plan used wrong shape (string for int) | Skip with a note |

### Idempotency

Re-running seed-data shouldn't pile up duplicates. Pick one strategy based on the schema:

1. **Natural-key match** (preferred when one exists) — before inserting, check whether a row with the same `email` / `sku_code` / display name already exists. If so, skip.
2. **Seed tag** — if the schema has a free-text column (e.g., `notes`, `metadata`), set it to `seed:<branch>-<short-sha>`. On re-run, query existing tagged rows and skip if matched.
3. **None** — if neither works, insert anyway and let UNIQUE constraints catch collisions. Note this in the summary.

The plan's "Notes" section may state a preferred strategy. Otherwise pick (1) for tables with obvious natural keys and (2) for the rest.

## Step 5: Verify

After all inserts, re-query row counts and compare to the planned increase (e.g., plan called for 14 new SKUs, before-count was 0, after-count should be 14 minus any skipped/failed).

List any tables where the post-count is below the expected number and explain why (skips, failures).

## Step 6: Report

Print a chat summary:

```
Seeded from ai_docs/feature/abc-123-add-skus/data-plan.md

Mechanism: python manage.py shell (Django ORM)
Idempotency: natural-key match on email/name

| Table       | Before | Inserted | Skipped | Failed | After |
|-------------|-------:|---------:|--------:|-------:|------:|
| users       |     12 |        0 |       4 |      0 |    12 |
| categories  |      1 |        5 |       0 |      0 |     6 |
| skus        |      0 |       13 |       0 |      1 |    13 |

Skipped:
  • 4 users — natural-key match on email (already present)

Failed:
  • 1 sku — CHECK constraint on price (stupid-path row had price=0; constraint is price > 0).
    Suggest: re-run /check-data so the plan respects this constraint.

Ready for /qa-ticket.
```

## Edge cases

- **Plan file missing**: tell the user to run `/check-data` first; do not guess at data.
- **Plan file stale** (older than HEAD): warn, offer to continue or stop.
- **DB not reachable**: stop. Don't silently fall back to API — ask the user to start the DB.
- **Project seed script + plan extras**: run the seed script for the rows it covers, then top up edge / error / stupid rows via mechanism 3b or 3c.
- **Unique constraint conflicts on re-run**: skip and report. Never delete-and-reinsert — the user may have intentional data.
- **FK ordering not clear**: insert parents first inferred from model FK declarations; if there's a cycle, ask the user.
- **Schema drift** (column referenced by the plan no longer exists): skip the affected rows and surface "schema drift — re-run /check-data".
- **Mongo / non-relational**: collections instead of tables; `insertOne` / `insertMany`; idempotency via `_id` or natural-key fields.
- **Plan references PK placeholders** like `<users.id of Alice>`: resolve them from the rows you've already inserted in this run. If "Alice" wasn't inserted (e.g., skipped as already-present), look her up by natural key first.
- **HTTP POST mode and the endpoint requires auth**: read the project's dev-mode auth setup (test-mode bypass, localStorage mock, or service token in `.env`). If none of those work, stop and ask the user.
