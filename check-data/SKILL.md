---
name: check-data
description: "Plans the data the local DB needs to properly QA the current branch. Inspects branch diff + ticket + DB, then writes a markdown plan to `ai_docs/<branch>/data-plan.md` (or `.notes/<branch>/data-plan.md` if `.notes/` exists) covering happy / edge / error / stupid-path rows. Trigger on 'check data', 'data readiness', 'plan seed data', 'what data do I need', or '/check-data'. Does NOT generate test cases (use `/qa-ticket`) or insert data (use `/seed-data`). Supports Linear (default) and Jira — pass 'jira' as 2nd arg."
---

# Check Data

Plan the data your local database needs so the current branch's feature can be tested under realistic conditions — typical rows, boundary values, problematic states, and pathological inputs. Writes a markdown report. Does **not** insert anything (that's `/seed-data`) and does **not** generate test cases (that's `/qa-ticket`).

## Why this exists

QA against an empty or sparse DB produces false confidence — lists look fine because they're empty, filters work because there's nothing to filter, encoding bugs never surface because no row contains an emoji. "One row of test data" hides almost everything interesting.

Good QA needs **varied** data across four buckets:

- **Happy path** — typical valid rows. Confirms the default flow works at all.
- **Edge cases** — still valid, on the boundary: max-length strings, single-char names, empty optional fields, min/max numerics. Catches off-by-one, layout breakage, pagination glitches.
- **Error paths** — rows representing real-world DB messiness: soft-deletes, deprecated enum values, half-migrated rows, stale timestamps, missing optional refs. Confirms the feature handles imperfect data instead of assuming a clean schema.
- **Stupid paths** — pathological-but-storable content: unicode, emoji, HTML/script tags, very long strings, control chars, leading/trailing whitespace, SQL-injection-shaped strings. Verifies display, encoding, and escaping hold up against inputs nobody *should* send but inevitably will.

This skill plans rows in those four buckets per table. `/seed-data` reads the plan and inserts. `/qa-ticket` exercises the feature against the seeded state.

## Step 1: Extract ticket and gather context

Run 1a-1d in parallel — they're independent.

### 1a. Parse optional platform argument

If the user passed an argument (e.g., `/check-data jira`), set **platform** to that value. Supported: `linear` (default), `jira`. Anything else → default to `linear` and note it in the report.

### 1b. Extract ticket ID from branch

```bash
git rev-parse --abbrev-ref HEAD
```

Match the pattern `[a-zA-Z]{2,5}-\d+` case-insensitively and uppercase the result (e.g., `feature/abc-123-add-skus` → `ABC-123`). If no match, that's OK — the diff alone is enough to plan data. Only ask the user for an ID if they explicitly want ticket context in the report.

### 1c. Fetch ticket details

**Linear** (default):
```bash
linear issue view <TICKET-ID>
```

**Jira**:
```bash
jira issue view <TICKET-ID> --plain
```

Pull title, description, acceptance criteria. The ticket clarifies *what behavior* the data must exercise (e.g., "filter by status", "search by name with pagination"). If the CLI is missing or the fetch fails, proceed with the diff alone — note "no ticket context" in the report.

### 1d. Fetch code diff against develop

```bash
git diff develop...HEAD --stat
git diff develop...HEAD
```

The diff is the authoritative source for *which tables changed* — even if the ticket is vague or missing, the diff tells you what data the feature touches.

## Step 2: Map data dependencies

From the diff, identify which tables/collections the feature touches and the **role** each plays. The role determines how much data and what variety it needs.

| Role | Signals in diff | Data need |
|------|-----------------|-----------|
| **CRUD target** | New/changed create/update/delete handlers; new migration; new model | Some existing rows for list/filter views; tests can add more |
| **Read/display target** | Changed list/detail handlers; new query joins; new dashboard component | 3-5 rows minimum, more if the view paginates |
| **Lookup/reference** | New FK column; new dropdown options; enum-like dimension table | ≥1 valid row, plus an inactive/deprecated one if soft-delete or enum-state exists |
| **Filter/search target** | New `WHERE`, `ILIKE`, search index, filter UI | ≥5-10 rows with *varied* values across the filtered columns |

Also flag **FK dependencies** — if the feature creates `orders`, the plan needs valid `users` to exist as FK targets, even if `users` isn't directly touched by the diff.

## Step 3: Inspect the database

### 3a. Discover database access

Read the repository to figure out how to reach the DB. Check in this order:

1. **`docker-compose.yml` / `docker-compose.*.yml`** — DB service name, ports, credentials, volume mounts.
2. **`docker ps`** — running DB containers (postgres, mysql, mongo, etc.).
3. **Environment files** (`.env`, `.env.local`, `.env.development`) — `DATABASE_URL`, host/port/user/password.
4. **Framework config** — `settings.py` (Django), `config/database.yml` (Rails), `prisma/schema.prisma`, `knexfile.js`, `ormconfig.ts`.

Capture engine, host, port, db name, user, container name. The report records these so `/seed-data` doesn't have to rediscover.

### 3b. Query row counts

Use the most direct path. Combine all counts into one call where possible:

```bash
# Postgres in Docker
docker exec <container> psql -U <user> -d <db> -c "SELECT 'users' tbl, count(*) FROM users UNION ALL SELECT 'orders', count(*) FROM orders"

# MySQL in Docker
docker exec <container> mysql -u <user> -p<pass> <db> -e "SELECT 'users' tbl, count(*) FROM users UNION ALL SELECT 'orders', count(*) FROM orders"

# SQLite
sqlite3 <path/to/db.sqlite3> "SELECT 'users', count(*) FROM users UNION ALL SELECT 'orders', count(*) FROM orders;"

# Mongo
docker exec <container> mongosh <db> --eval "['users','orders'].forEach(c => print(c, db[c].countDocuments()))"
```

Prefer the project's own DB CLI if it exists (`python manage.py dbshell`, `rails dbconsole`) — credentials are already wired and you don't have to read them out of `.env`.

### 3c. Look for an existing seed mechanism

Search for `seed`, `fixtures`, `factories`, `sample_data` in:
- `Makefile`, `package.json` scripts
- `manage.py` commands (Django)
- `db/seeds*` (Rails)
- `prisma/seed.*`
- top-level `scripts/seed*`, `cmd/seed*`

Note the path/command in the report. `/seed-data` prefers this over raw inserts because project seed scripts already know about model defaults, signals, and FK ordering.

### 3d. Read the schema for the tables in scope

For each table identified in Step 2, glance at the schema (model definition, migration, or `DESCRIBE <table>`) and note:
- Column names, types, nullability, max lengths
- Constraints (UNIQUE, CHECK, FK targets)
- Defaults

This is what lets you write **insertable** rows in Step 4 — every planned row must satisfy the schema.

## Step 4: Plan the data

For each table in scope, propose rows across the four buckets. For every row include:

- A concrete **shape** — field-level values (or a sketch when exact PKs/FKs depend on insertion order; use placeholders like `<users.id of Alice>`).
- A **why** — which scenario this row unlocks (one sentence).

Keep counts reasonable: roughly 3-5 happy rows, 2-4 per other bucket per table. The goal is *coverage*, not volume. If the table is a small lookup with only 3 valid enum values, 3 rows is plenty.

### Buckets

**Happy path** — typical valid rows. Realistic strings, mid-range numerics, normal dates, common enum values. Vary names/values across rows so list views show diversity (don't seed three rows all named "Test").

**Edge cases** — still valid, on the boundary:
- Max-length name; single-char name
- Empty optional fields (NULL or `""`)
- Numerics at column min and max
- Earliest and latest valid dates
- Just-under / just-at any soft limit the code enforces (e.g., if there's a `max_items_per_user = 10`, seed a user with exactly 10 items)

**Error paths** — valid for insertion but representing imperfect real-world state:
- Soft-deleted rows (rows with `deleted_at` set, if the column exists)
- Deprecated/legacy enum values still in the table (e.g., `status = "pending_verification"` after that state was removed from the UI)
- Rows missing optional refs the UI assumes exist (null `avatar_url`, missing `team_id`)
- Half-migrated rows (older schema fields populated, newer ones null)
- Stale timestamps (`created_at` years ago — exposes "X days ago" formatting bugs)

**Stupid paths** — pathological-but-storable content:
- Unicode (CJK, Arabic, Hebrew, combining diacritics)
- Emoji, including ZWJ sequences like 👨‍👩‍👧‍👦
- HTML/script tags in display fields: `<script>alert(1)</script>`, `<b>bold</b>`, `&amp;`
- Very long strings *just under* the column limit
- Newlines, tabs, and other control chars inside text fields
- Leading and trailing whitespace
- SQL-injection-shaped strings: `'; DROP TABLE users; --`
- Mixed RTL/LTR sequences

Every row must satisfy the schema — if a column is NOT NULL or has a CHECK constraint, respect it. The point of stupid paths is to stress display and encoding, not to break the DB at the insertion layer.

### What NOT to include

- Rows the DB *must* reject (FK to non-existent target, duplicate PK, type mismatch) — those are test inputs for `/qa-ticket` to throw at endpoints, not seed data.
- Test cases, expected outcomes, assertions — that's `/qa-ticket`'s job.
- Bulk fixture dumps. Keep the plan reviewable.

## Step 5: Write the report

### 5a. Pick output directory

At the repo root:
- If `.notes/` already exists → use `.notes/`.
- Else → use `ai_docs/` (create if missing).

Then ensure `<output-dir>/<branch-name>/` exists (mkdir -p — branches with slashes like `feature/abc-123-x` create nested directories, which is intentional).

### 5b. Write `data-plan.md`

If the file already exists, ask the user before overwriting — they may have hand-edited it. Offer to diff (`git diff --no-index` against `/tmp`) so the user can see what would change.

Use this template:

```markdown
# Data Plan: <branch-name>

- **Ticket**: <TICKET-ID> — <title>   *(or "no ticket")*
- **Platform**: linear | jira
- **Date**: <YYYY-MM-DD>
- **Output dir**: ai_docs | .notes

## DB Connection
- **Engine**: postgres | mysql | sqlite | mongo
- **Host / Port**: <host>:<port>
- **Database**: <db_name>
- **User**: <user>
- **Container**: <container_name>   *(or "n/a")*
- **Project CLI**: <e.g., "python manage.py dbshell">   *(or "none")*
- **Existing seed mechanism**: <path/command>   *(or "none")*

## Tables in scope

| Table       | Current rows | Role                   | Notes |
|-------------|-------------:|------------------------|-------|
| users       | 12           | Lookup (FK target)     | Healthy |
| skus        | 0            | CRUD target            | Empty — must seed |
| categories  | 1            | Filter/search target   | Sparse — add variety |

## Suggested data: `skus`

### Happy path
- `{ name: "Widget A", category_id: <categories.id widgets>, price: 19.99, status: "active" }` — Why: typical active SKU, populates default list.
- `{ name: "Widget B", category_id: <categories.id widgets>, price: 24.50, status: "active" }` — Why: second active SKU for list-shows-multiple test.
- `{ name: "Gadget X", category_id: <categories.id gadgets>, price: 99.00, status: "active" }` — Why: different category, exercises category filter.

### Edge cases
- `{ name: "A", category_id: <categories.id widgets>, price: 0.01, status: "active" }` — Why: single-char name + min price, boundary on display ellipsis and currency formatting.
- `{ name: "<255-char string>", category_id: <categories.id widgets>, price: 9999.99, status: "active" }` — Why: max name length + max price, boundary on column width.

### Error paths
- `{ name: "Old SKU", category_id: <categories.id widgets>, price: 5.00, status: "active", deleted_at: "2024-01-01" }` — Why: soft-deleted, should be hidden from default views.
- `{ name: "Legacy SKU", category_id: <categories.id widgets>, price: 5.00, status: "pending_review" }` — Why: deprecated status still in DB, exercises status-filter resilience.

### Stupid paths
- `{ name: "李雷 🎉 Widget", category_id: <categories.id widgets>, price: 12.00, status: "active" }` — Why: CJK + emoji in name, exercises encoding and display width calculation.
- `{ name: "<script>alert(1)</script>", category_id: <categories.id widgets>, price: 12.00, status: "active" }` — Why: HTML/script in display field, exercises escaping in list and detail views.

## Suggested data: `categories`
*(... same structure for each table ...)*

## Notes & warnings
- FK ordering: insert `categories` before `skus`.
- `skus.name` has UNIQUE constraint — avoid name collisions across buckets.
- `skus.created_at` defaults to now() — to seed "stale" rows, explicitly set it.
- `categories` table has no soft-delete column; error-path bucket for categories uses deprecated `kind` values instead.
```

## Step 6: Print summary in chat

Brief recap so the user can decide whether to proceed:

```
Wrote data plan to ai_docs/feature/abc-123-add-skus/data-plan.md

Tables in scope:
  • users       (12 rows now)  → no action needed (FK target, sufficient)
  • categories  (1 row now)    → seed ~5 more
  • skus        (0 rows now)   → seed ~14 (3 happy / 2 edge / 2 error / 2 stupid + others)

Existing seed mechanism: scripts/seed.py (covers happy path only)

Review the plan, then run /seed-data to load it.
```

## Edge cases

- **No ticket ID in branch and no arg**: proceed using diff only; ticket section in the report says "no ticket".
- **Platform CLI missing**: skip the ticket fetch, note in report; the diff is still authoritative.
- **No DB found**: write the report with diff-derived tables and a `DB Connection` block marked "not discovered". Suggest the user clarify connection details or start their DB.
- **Branch has no diff vs develop**: report "no changes relative to develop" and exit without writing.
- **Branch name with slashes**: keep them — they create subdirectories under `ai_docs/` / `.notes/`. Intentional.
- **Plan file already exists**: ask before overwriting; offer to show a diff.
- **Mongo / non-relational store**: replace "tables" with "collections" throughout; query counts via `countDocuments`; FKs are usually embedded refs, so note that explicitly.
- **Multiple DBs / microservices**: one `## DB Connection` block per DB, with tables grouped under each.
- **Unknown platform argument**: default to Linear with a note in the report.
- **Jira CLI not installed**: report and suggest `brew install ankitpokhrel/jira-cli/jira-cli`; proceed with diff-only context.
- **Schema has a NOT NULL column the plan would test as null**: respect the schema — use a sentinel value instead (empty string, `"n/a"`, etc.) and explain in the row's "Why".
