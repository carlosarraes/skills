# Triage facts (volatile — CLIs: `mb --llm`, `dog --help` are the source of truth)

Environment-specific ids, hostnames, and project keys are **not** recorded here. Ask the
user for them, or check memory if a previous session saved them. Never guess a database
id or a backoffice hostname — a wrong one silently returns empty or unrelated results.

## Metabase (`mb`)

Databases are referenced by name or id (case-insensitive). The set of databases and their
ids is deployment-specific: run `mb databases` to list them, or ask the user which database
maps to prod, staging, and each region. Default to the staging database for anything
reproducible outside production.

```bash
mb databases                    # discover ids before querying
mb query <db> "SELECT ..."      # name or id, case-insensitive; --json/--csv
mb fields <db> <table>          # column names/types before guessing
```
If `mb` returns an auth error the session token expired — only the interactive `mb config` fixes it; tell the user, don't retry.

## Datadog (`dog`)

```bash
dog logs 'env:prod service:api status:error' --since 3h --format jsonl
dog logs 'env:<staging-env-tag> @module:<module>' --since 24h --limit 20
dog logs '<subscription_id> OR <charge_id> OR <company_id>' --since 8h   # bare-ID search works
```
- Env tags are literal and rarely match the informal name for the environment (a staging env is often tagged something other than `hml`/`stg`). Confirm the exact tag with the user or `dog` itself before filtering on it.
- `@module:` matches `LoggerService(module=...)`; `@event:` supports globs (`@event:*overage*`).
- **Always pass `--since`** — the default is 15m.

## Backoffice (visual cross-check links for the report)

The backoffice hostnames per environment/region are deployment-specific — ask the user or
check memory. Once known, the paths are stable:

- Companies: `https://<backoffice-host>/dashboard/companies/<id>`
- Plans: `https://<backoffice-host>/dashboard/plansv2/<id>`

## Jira (only after explicit approval)

```bash
jira issue create -tTask -s"<title>" -b"<description>" --no-input   # confirm the project key with the user
```
`--no-input` is mandatory headless; without it the command prompts and hangs. The default
project key comes from the local `jira` config — verify it is the right one before creating.

## Card proposal shape (in the report, not in Jira)

- Title: imperative, one line, in the team's working language.
- Story points: 1/2/3/5 with a one-clause justification.
- Description: brief, focused on where to touch (the team's convention), citing the evidence trail.
