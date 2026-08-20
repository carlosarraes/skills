---
name: triage-incident
description: Use when a production or staging symptom, alert, or stakeholder report needs a read-only evidence-backed bug-versus-expected-behavior verdict.
---

# Triage Incident

Turn a pasted symptom into a verdict the developer can forward: **bug** or **expected behavior**, with the evidence trail.

## Done means

A short report containing: (1) the verdict — bug / expected / needs-more-data, stated first; (2) the evidence behind it — the Metabase rows, the Datadog log lines, and the code path (`file:line`) that explain the behavior; (3) affected entities (company ids, subscription ids); (4) suggested next step — including, when it's a bug, a proposed card (title + story points + brief description in the team's working language) **offered, not created**.

## Hard constraints

- **Read-only.** Queries and log reads only — no data changes, no fixes, no reruns of jobs.
- **Never create a Jira card (or comment on one) without explicit approval.** Propose the card in the report; the user files it or says "create it".
- **Every claim in the verdict cites its evidence** — a query result, a log line, or a file:line. A claim you cannot back with one of those is labeled a hypothesis, not stated as fact.

## Flow

Investigate however the symptom demands — typical spine: reproduce the number the PM saw (Metabase) → find the code's own account of why (Datadog events) → read the code path that emitted it → verdict. Query tags, discovery commands, and CLI gotchas: [references/triage-facts.md](references/triage-facts.md) — read it before the first query; the default-window and env-tag gotchas silently return empty results otherwise. Environment ids and backoffice hostnames are not hardcoded anywhere in this skill: ask the user, or check memory for a previous session's answer.

## Common mistakes

| Mistake | Reality |
|---|---|
| `dog logs` with no `--since` | Default window is 15 minutes — you'll miss the incident and conclude "no logs". |
| Guessing the staging `env:` tag | The literal tag rarely matches the informal name. Confirm it; an empty result ≠ no events. |
| Filing the follow-up card right away | Cards are proposed in the report and created only on explicit approval. |
| Inventing a database id or backoffice host | Discover them (`mb databases`) or ask the user. A wrong id returns plausible, unrelated rows. |
| Stating an inference as fact | If it isn't backed by a row, a log line, or file:line, it's a hypothesis — say so. |
| Querying prod by reflex | Staging reproduces most symptoms; touch prod when the symptom is prod. |
