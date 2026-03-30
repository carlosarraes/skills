---
name: qa-ticket
description: "Automates QA testing for the current branch by extracting the Linear ticket ID (e.g., ABC-123, XYZ-456) from the git branch, fetching ticket details and code diff, generating a targeted test plan, and executing backend (curl) and frontend (agent-browser) tests. Fixes bugs found during testing and retries. Use this skill whenever the user asks to 'QA this branch', 'test this ticket', 'run QA', 'qa-ticket', 'test my changes', 'verify this works', 'smoke test this', 'run acceptance tests', or wants automated testing of their current feature branch against localhost. Also trigger when the user mentions 'acceptance testing', 'manual QA', 'end-to-end test my changes', or 'does this work'. Supports Linear (default) and Jira — pass 'jira' as argument to use Jira (e.g., '/qa-ticket jira')."
---

# QA Ticket

Automatically QA-test the current branch by analyzing the Linear ticket and code changes, then executing targeted backend and frontend tests against the local dev environment.

## Prerequisites

Before running any tests, discover the project's local dev setup. Check CLAUDE.md, README.md, docker-compose.yml, package.json scripts, or Makefile for:

- **Backend URL** (e.g., `localhost:8000`, `localhost:3000`)
- **Frontend URL** (e.g., `localhost:8080`, `localhost:3001`)
- **Auth setup** — whether a test/dev mode bypasses auth, or if credentials are needed
- **Platform CLI** — `linear` or `jira` CLI authenticated (depending on platform argument)

Quick health check (run in parallel, replace ports with discovered values):
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:<BACKEND_PORT>/docs
curl -s -o /dev/null -w "%{http_code}" http://localhost:<FRONTEND_PORT>
```

If backend returns non-200, skip backend tests and note in report. Same for frontend.

---

## Step 1: Extract ticket and gather context

Run all three in the **same turn** (parallel Bash calls) since they're independent.

### 1a. Parse optional platform argument

If the user passed an argument (e.g., `/qa-ticket jira`), set **platform** to that value. Supported values: `linear` (default), `jira`. If no argument or unrecognized value, default to `linear`.

### 1b. Extract ticket ID from branch name

```bash
git rev-parse --abbrev-ref HEAD
```

Extract the ticket ID using a **case-insensitive** match — branches are typically lowercase (e.g., `feature/abc-123-add-sku-validation`, `feature/xyz-456-fix-bug`). Match the pattern `[a-zA-Z]{2,5}-\d+` and uppercase it (e.g., `ABC-123`, `XYZ-456`) for the platform CLI.

If no ticket ID pattern is found, ask the user: "Could not extract a ticket ID from branch `<name>`. What's the ticket ID (e.g., ABC-123, XYZ-456)?"

### 1c. Fetch ticket details

**Linear** (default):
```bash
linear issue view <TICKET-ID>
```

**Jira**:
```bash
jira issue view <TICKET-ID> --plain
```

Extract: title, description, labels, priority, acceptance criteria (often in the description). The description defines what to test.

### 1d. Fetch code diff against develop

```bash
git diff develop...HEAD --stat
git diff develop...HEAD
```

Parse the diff to understand:
- Which backend modules changed (e.g., `backend/src/proposition_manager/`)
- Which frontend components changed (e.g., `frontend/src/pages/`)
- Whether changes are backend-only, frontend-only, or fullstack
- What API endpoints are affected (route definitions, handlers)
- What models/schemas changed

---

## Step 2: Analyze and create test plan

Based on the ticket description + code diff, create a **targeted** test checklist. Only test what the changes actually affect.

### Categorize changes

- **Backend API**: route handlers, services, models, database logic
- **Frontend UI**: React components, pages, hooks, forms
- **Fullstack**: changes spanning both sides

### Generate test cases

Each test case has:
- **ID**: T1, T2, T3, etc.
- **Type**: `backend` or `frontend`
- **Category**: `happy-path`, `error`, or `edge-case`
- **Description**: What it verifies (tied to a ticket requirement or code change)
- **Steps**: Concrete actions
- **Expected result**: What success looks like

### Test coverage requirements

Good QA means testing all three categories thoroughly. Skipping errors and edge cases leads to false confidence. Follow this checklist when generating tests:

#### 1. Happy path (the feature works as intended)
- Every new/changed endpoint gets at least one success test
- Full CRUD cycle if applicable (create → read → update → list → delete)
- Frontend: primary user flow end-to-end (navigate → interact → verify result)

#### 2. Error handling (the feature fails gracefully)
- **Validation boundaries**: For every validator in schemas/models (min_length, max_length, regex, required fields, enum values), test both sides of the boundary. E.g., if max_length=2000, test with 2000 chars (pass) and 2001 chars (fail).
- **Missing/invalid fields**: Omit each required field one at a time. Send wrong types (string where int expected, etc.).
- **Permission checks**: If the code has authorization logic (e.g., "only author can delete"), test the unauthorized path explicitly — use a different user ID or simulate a forbidden action.
- **Resource not found**: Test with non-existent IDs (valid UUID format but doesn't exist in DB).
- **Duplicate/conflict errors**: If the code prevents duplicates or has optimistic concurrency (ETags, revisions), test the conflict case.
- **Rate limiting**: If endpoints have rate limits (check for `@limiter.limit`), note it in the plan (no need to actually hit the limit, just document it exists).
- **Frontend error states**: Submit invalid data through the UI and verify error messages/toasts appear. Test what happens when the API returns an error.

#### 3. Edge cases (boundary conditions and unusual inputs)
- **Capacity limits**: If the code enforces limits (e.g., max 100 items), test at the boundary. If feasible, test what happens when the limit is reached.
- **Empty states**: What does the UI show with zero items? What happens when you delete the last item?
- **Special characters**: Test inputs with unicode, emoji, HTML tags, very long strings, newlines.
- **Concurrent operations**: If relevant, test what happens with rapid sequential requests (e.g., double-click submit).
- **Multiple items**: Don't just test with one item — add 2-3, verify they all appear, delete one and verify the others remain.
- **Keyboard interactions**: If the frontend code has keyboard handlers (onKeyDown, onKeyPress), test those paths (e.g., Enter to submit).
- **State transitions**: If the feature involves state changes (open/close, expand/collapse, draft/published), test toggling back and forth.

### What NOT to test
Unchanged modules, authentication (bypassed by ENVIRONMENT=test), infrastructure, code style.

### Print the plan before executing

Group by category so coverage gaps are visible:

```
## Test Plan for <TICKET-ID>: <ticket title>

### Backend Tests — Happy Path
- [ ] T1: POST /api/<resource> with valid payload creates a record (201)
- [ ] T2: GET /api/<resource>/:id returns the created record (200)

### Backend Tests — Errors
- [ ] T3: POST /api/<resource> with missing required field returns 422
- [ ] T4: POST /api/<resource> with empty string for required field returns 422
- [ ] T5: DELETE /api/<resource>/:id by non-owner returns 403
- [ ] T6: GET /api/<resource>/:nonexistent returns 404

### Backend Tests — Edge Cases
- [ ] T7: POST /api/<resource> with max-length field (boundary)
- [ ] T8: POST /api/<resource> with unicode/emoji in text field

### Frontend Tests — Happy Path
- [ ] T9: Creation form submits and shows in table/list

### Frontend Tests — Errors
- [ ] T10: Validation error appears when required field is left empty

### Frontend Tests — Edge Cases
- [ ] T11: Submit via Enter key (not just button click)
- [ ] T12: Empty state shows correct message
```

---

## Step 3: Execute backend tests

Use `curl` against the backend URL discovered in Prerequisites. If the project runs in a test/dev mode that bypasses auth, no Authorization header is needed. Otherwise, include the appropriate auth header.

### Curl patterns

**GET (list)**:
```bash
curl -s -w "\n%{http_code}" http://localhost:<BACKEND_PORT>/api/<resource>
```

**POST (create)**:
```bash
curl -s -w "\n%{http_code}" -X POST http://localhost:<BACKEND_PORT>/api/<resource> \
  -H "Content-Type: application/json" \
  -d '{"field": "value"}'
```

**PUT/PATCH (update)**:
```bash
curl -s -w "\n%{http_code}" -X PATCH http://localhost:<BACKEND_PORT>/api/<resource>/<id> \
  -H "Content-Type: application/json" \
  -d '{"field": "updated_value"}'
```

**DELETE**:
```bash
curl -s -w "\n%{http_code}" -X DELETE http://localhost:<BACKEND_PORT>/api/<resource>/<id>
```

### Result evaluation

- Parse HTTP status code from the last line (`%{http_code}` output)
- Parse JSON response body (everything before the status code line)
- **PASS**: status code matches expectation AND response body contains expected data
- **FAIL**: status code mismatch OR response body doesn't match

### CRUD test sequencing

When testing CRUD on a resource, follow this order to manage test data:
1. **Create** (POST) — capture the returned `id` or `_id`
2. **Read** (GET by id) — verify it's retrievable
3. **Update** (PATCH/PUT) — modify a field, verify the change
4. **List** (GET all) — verify it appears
5. **Delete** (DELETE) — clean up
6. **Verify delete** (GET by id) — confirm 404

### Discovering API routes

Discover available routes from the project. Try these approaches in order:

1. **OpenAPI/Swagger spec** (if the backend serves one):
   ```bash
   curl -s http://localhost:<BACKEND_PORT>/openapi.json | python3 -c "import sys,json; paths=json.load(sys.stdin)['paths']; [print(p) for p in sorted(paths)]"
   ```
2. **Route files in the codebase** — search for route definitions (e.g., `@app.get`, `@router.post`, `app.use`, `Router()`)
3. **Code diff** — the diff from Step 1d already shows which route files changed; focus on those

---

## Step 4: Execute frontend tests

When the test plan includes frontend tests, **load the agent-browser skill first** using the Skill tool:

```
Skill: agent-browser
```

This gives you access to `agent-browser` commands for browser automation.

### Frontend auth setup

Discover how the frontend handles authentication in dev/test mode. Check CLAUDE.md, README.md, or the frontend source for:

- **Test mode bypass** — some apps skip auth entirely when `ENVIRONMENT=test` or similar
- **localStorage/cookie mock** — if the app reads a cached session from localStorage, seed it before navigating. Look for the localStorage key name and expected shape in the auth code
- **Login flow** — if no bypass exists, use `agent-browser` to log in through the UI with test credentials

Example pattern for localStorage-based auth:
```bash
agent-browser open http://localhost:<FRONTEND_PORT> && agent-browser wait --load networkidle
agent-browser eval "localStorage.setItem('<AUTH_KEY>', JSON.stringify(<MOCK_SESSION>)); 'done'"
```

After setting auth, navigate to the target page.

### Navigation

Navigate directly to the relevant page:

```bash
agent-browser open http://localhost:<FRONTEND_PORT>/<route> && agent-browser wait --load networkidle && agent-browser snapshot -i
```

### Discovering frontend routes

Don't assume route paths — discover them from the project:

1. **Code diff** — the changed frontend files from Step 1d indicate which pages/routes are affected
2. **Router config** — search for route definitions (e.g., `<Route path=`, `createBrowserRouter`, `next.js app/ or pages/` directory structure)
3. **Navigation from home** — open the root URL, take a snapshot, and follow links to the relevant page

### Interaction pattern

For every frontend test, follow this cycle:

1. **Navigate** to the target page
2. **Snapshot** (`agent-browser snapshot -i`) to discover interactive elements and their refs
3. **Interact** (click, fill, select) using refs from the snapshot
4. **Wait** for the action (`agent-browser wait --load networkidle`)
5. **Re-snapshot** to verify the result — refs are invalidated after DOM changes, so you must always re-snapshot
6. **Assert** by checking snapshot output for expected text, elements, or state changes

### Example: testing a form

```bash
# Navigate
agent-browser open http://localhost:<FRONTEND_PORT>/<route> && agent-browser wait --load networkidle

# Discover elements
agent-browser snapshot -i
# Output: @e1 [button] "Add SKU", @e2 [table] ...

# Click add
agent-browser click @e1
agent-browser wait --load networkidle
agent-browser snapshot -i
# Output: @e3 [input] "Name", @e4 [input] "Description", @e5 [button] "Save"

# Fill and submit
agent-browser fill @e3 "Test SKU"
agent-browser fill @e4 "Created by QA automation"
agent-browser click @e5
agent-browser wait --load networkidle

# Verify
agent-browser snapshot -i
# Look for success toast, new table row, or navigation to detail page
```

### Frontend assertions

- **Element presence**: Check snapshot output for expected text
- **Navigation**: `agent-browser get url` to verify URL changed
- **Error states**: After invalid submission, snapshot and look for validation messages
- **Visual**: `agent-browser screenshot` if needed for manual review

### Important agent-browser rules

- Always re-snapshot after any click, navigation, or form submission
- Use `agent-browser wait --load networkidle` after actions that trigger API calls
- If snapshot shows a loading spinner, wait and re-snapshot
- If element not found, scroll (`agent-browser scroll down 500`) and re-snapshot
- **Radix UI workaround**: Some Radix primitives (Collapsible, Dialog triggers, Accordion) may not respond to `agent-browser click @ref`. If a click doesn't change the element's state (e.g., `expanded` stays `false`), fall back to a JS click via eval:
  ```bash
  agent-browser eval --stdin <<'EVALEOF'
  const btn = document.querySelector('button[data-state="closed"]');
  if (btn) btn.click();
  EVALEOF
  ```
  Then wait and re-snapshot to verify the state changed.

---

## Step 5: Fix-and-retry loop

When a test fails, don't immediately mark it as failed. Attempt to diagnose and fix.

### Protocol (max 3 attempts per test)

1. **Attempt 1**: Run the test as designed
2. **On failure — diagnose**:
   - Backend: read error response body, check server logs if unclear
   - Frontend: `agent-browser screenshot`, check snapshot for error messages
3. **Identify root cause**:
   - **Code bug**: Fix the file, wait for hot-reload, retry
   - **Test bug**: Adjust test parameters (wrong URL, payload, expected value), retry
   - **Environment issue**: Server down, DB not seeded — report and skip
4. **Attempt 2**: Re-run after fix
5. **On second failure**: Diagnose again, try another fix
6. **Attempt 3**: Final retry
7. **After 3 failures**: Mark as **FAILED**, record full details

### Fix guidelines

- Make minimal changes — don't refactor unrelated code
- After editing backend files, wait ~2 seconds for uvicorn hot-reload
- After editing frontend files, wait for Vite HMR (`agent-browser wait --load networkidle`)
- If unsure about a fix, read surrounding code for context first

---

## Step 6: Generate report

After all tests complete (or fail after 3 attempts), output the report directly in the conversation.

### Report format

```
# QA Report: <TICKET-ID> — <ticket title>

**Branch**: <branch name>
**Ticket**: <TICKET-ID>
**Date**: <current date>
**Result**: X/Y tests passed

## Test Results

| # | Type | Category | Test | Result | Attempts | Notes |
|---|------|----------|------|--------|----------|-------|
| T1 | Backend | Happy path | POST /api/items creates record | PASS | 1 | — |
| T2 | Backend | Error | POST /api/items missing name → 422 | PASS | 1 | — |
| T3 | Backend | Edge case | POST /api/items with 2000-char name | PASS | 1 | — |
| T4 | Frontend | Happy path | Form submission | PASS | 2 | Fixed missing field validation |
| T5 | Frontend | Error | Validation error display | FAIL | 3 | Toast not appearing |
| T6 | Frontend | Edge case | Enter key submits form | PASS | 1 | — |

## Fixes Applied

### T3 (attempt 2)
- **File**: `backend/src/<module>/routes/<resource>.py:45`
- **Change**: Added missing required field validation
- **Why**: Payload was accepted without required field, causing 500 on DB insert

## Failed Tests — Details

### T4: Validation error display
- **Expected**: Error toast when submitting empty name
- **Actual**: Form submits without validation, returns 500
- **Root cause**: Missing Zod validation on frontend form schema
- **Attempts**: 3 — added zod rule → still failed → checked backend → also missing validation

## Summary

<2-3 sentences: what works, what doesn't, whether acceptance criteria are met, recommended follow-up>
```

### Report rules

- Show ALL tests, not just failures
- Keep PASS notes minimal
- For FAIL tests, include full details: expected vs actual, root cause, what was tried
- Explicitly state whether the ticket's acceptance criteria are satisfied
- List every file changed during fix-and-retry

---

## Edge cases

- **No ticket ID in branch** (case-insensitive): Ask the user for the ticket ID
- **Platform CLI fails**: Proceed with code diff only; note that test plan is based solely on changes
- **Jira CLI not installed**: If platform is jira but `jira` command not found, report error and suggest: `brew install ankitpokhrel/jira-cli/jira-cli`
- **Unknown platform argument**: If argument is not `linear` or `jira`, default to Linear with a note
- **Backend not running**: Skip backend tests, note in report
- **Frontend not running**: Skip frontend tests, note in report
- **No changes on branch**: Report "No changes found relative to develop" and stop
- **Only backend changes**: Skip frontend tests, note in report
- **Only frontend changes**: Skip backend tests, note in report
- **agent-browser unavailable**: Skip frontend tests, note in report
- **Test data collisions**: Use unique identifiers (timestamps) in test data names; clean up via DELETE after testing
