# QA Context and Preflight

Read this file before gathering setup, ticket, diff, or health context.

## Discover local setup first

Inspect only likely project-local sources: `CLAUDE.md`, `README.md`, `docker-compose.yml`, `package.json` scripts, and `Makefile`, then focused config/source when needed. Resolve:

- backend and frontend loopback URLs;
- test/dev authentication bypass, mock session, or test credentials;
- platform CLI availability/authentication;
- health-check routes.

Health-check discovered backend and frontend surfaces in parallel before functional testing. A nonhealthy surface is unavailable: retain its plan rows as `SKIP/INCONCLUSIVE` and report it. Do not fabricate an Authorization header when project auth is bypassed.

## Resolve ticket and diff independently

In the same parallel context-gathering turn:

1. Read the current branch.
2. Extract `[A-Za-z]{2,5}-\d+` case-insensitively and normalize it to uppercase. If absent, ask the user for the ticket ID before continuing.
3. Use explicit `linear` or `jira`; default an omitted or unknown platform to Linear and disclose an unknown-value fallback.
4. Fetch the ticket with `linear issue view <ID>` or `jira issue view <ID> --plain`.
5. Gather both `git diff develop...HEAD --stat` and `git diff develop...HEAD` regardless of provider success.

Extract ticket title, description, acceptance criteria, labels, and priority. Parse the diff for changed backend/frontend surfaces, endpoints, schemas, routes, models, and functional behavior.

Provider failure degrades to explicitly disclosed **diff-only** planning. Do not abort merely because Linear/Jira failed and do not infer unavailable requirements from branch wording. If the Jira CLI is missing, report it and include the current installation recovery suggested by the CLI/project docs rather than treating the ticket as fetched.

If the diff is empty, report exactly `No changes found relative to develop` and stop without inventing tests.

## Surface decisions

- Backend-only diff: plan/run backend; mark frontend not applicable.
- Frontend-only diff: plan/run frontend; mark backend not applicable.
- Full-stack diff: plan both; execute only healthy surfaces.
- Missing data: recommend `/check-data` then `/seed-data`; affected tests remain `SKIP/INCONCLUSIVE`, never PASS.

Validate provider syntax, project URLs/auth, base branch, and health assumptions against the current project before relying on them.
