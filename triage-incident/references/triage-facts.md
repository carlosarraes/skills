# acme triage facts (volatile — CLIs: `mb --llm`, `dog --help` are the source of truth)

## Metabase (`mb`)

| DB | id | use |
|---|---|---|
| Acme (prod) | `2` | prod symptoms |
| Homolog | `37` | default for anything reproducible in staging |
| Sandbox | `36` | |
| Acme-BR (prod BR) | `34` | BR-region prod |

```bash
mb query 37 "SELECT ..."        # name or id, case-insensitive; --json/--csv
mb fields 37 <table>            # column names/types before guessing
```
If `mb` returns an auth error the session token expired — only the interactive `mb config` fixes it; tell the user, don't retry.

## Datadog (`dog`)

```bash
dog logs 'env:prod service:api status:error' --since 3h --format jsonl
dog logs 'env:homolog @module:pagamentos.overage' --since 24h --limit 20
dog logs '<subscription_id> OR <charge_id> OR <company_id>' --since 8h   # bare-ID search works
```
- Env tags: `env:prod`, `env:homolog` (NOT `hml`).
- `@module:` matches `LoggerService(module=...)`; `@event:` supports globs (`@event:*overage*`).
- **Always pass `--since`** — the default is 15m.

## Backoffice (visual cross-check links for the report)

- Prod: `https://backoffice.acme.io/dashboard/companies/<id>` (BR: `br.backoffice.acme.io`)
- Homolog: `https://backoffice.hml.acme.io/dashboard/companies/<id>`
- Plans: `/dashboard/plansv2/<id>`

## Jira (only after explicit approval)

```bash
jira issue create -tTask -s"<title>" -b"<pt-br description>" --no-input   # project defaults to ZEX
```
`--no-input` is mandatory headless; without it the command prompts and hangs.

## Card proposal shape (in the report, not in Jira)

- Title: PT-BR, imperative, one line.
- Story points: 1/2/3/5 with a one-clause justification.
- Description: brief PT-BR, focused on where to touch (the team's convention), citing the evidence trail.
