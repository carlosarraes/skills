# Targeted Test Plan

Read this file before drafting or printing the plan. The plan is derived from **ticket plus diff**, restricted to changed functional behavior, and printed in full before any functional request or browser action.

## Case schema and grouping

Every case includes:

- **ID** (`T1`, `T2`, ...);
- **surface** (`backend` or `frontend`);
- **category** (`happy-path`, `error`, or `edge-case`);
- description tied to a ticket requirement or code change;
- concrete **steps**;
- **expected result** with observable status/content/URL/state.

Group the printed checklist by surface and category so gaps are visible. Never accept “happy path only” when changed behavior requires error or edge coverage.

## Coverage floor

### Backend

- At least one success test for **every changed endpoint**.
- When CRUD applies, one data lifecycle in this order: **create → read → update → list → delete → verify delete**.
- For every changed validator: exercise **both sides** of min/max/regex/range boundaries, each missing required field, wrong types, and invalid enum values.
- Exercise changed permission/authorization rules, valid-format **not found** IDs, duplicate/concurrency **conflict**, and frontend-facing API error behavior.
- Record a changed **rate limit** in the plan; do not stress-hit it merely to prove the annotation.

### Frontend

- Primary user flow end-to-end, including persisted/visible result.
- Validation and API error display.
- Relevant capacity and empty states.
- Special characters such as Unicode/emoji/HTML/newlines/long strings.
- Multiple items and deletion without corrupting remaining state.
- Relevant rapid/concurrent interactions, keyboard handlers, and state transitions.

Apply only items supported by ticket/diff behavior, but do not drop a supported case for speed.

## Scope exclusions

Exclude unchanged modules, infrastructure, code style, generated files, lockfile-only churn, unrelated docs, and authentication already bypassed by the project test mode. Diff presence alone does not make nonfunctional churn a test surface.

## Data readiness

This skill does not provision fixtures. Plan unique values and cleanup. If required data is missing, keep the affected case visible as `SKIP/INCONCLUSIVE`, state why, and recommend or invoke `/check-data` in its default plan, seed, and verify run before retrying.

Print the complete plan before execution. The report must later contain the same IDs; none may disappear.
