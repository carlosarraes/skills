---
name: ship-gitflow
description: Use when a completed ticket must ship through the twin production and staging Bitbucket branch, PR, and pipeline flow, or one leg needs completion.
---

# Ship Gitflow

Ship a finished ticket through the twin-branch flow: every ticket lands twice — once into `main` (production) and once into `homolog` (staging) — via two sibling branches carrying the same commits.

## Done means

- Both twins pushed: `{TICKET}-prd` based on `main` AND `{TICKET}-hml` based on `homolog`, each containing the ticket's commits (cherry-picked, same patches).
- One PR per twin, created with the exact invocation in [references/gitflow-facts.md](references/gitflow-facts.md).
- Both pipelines watched to completion. Green → report PR ids + pipeline results. Red → diagnose (`bt run view <id> --log-failed`), fix on the twin that failed, re-push, re-watch; mirror the fix to the other twin.

## Hard constraints

- **Never rewrite or force-push a branch that is already on origin.** Non-conforming commit messages on a pushed branch are not a reason to rebase it — leave them and follow the convention for any NEW commits.
- **Cherry-pick between twins; never merge** `main`/`homolog` into a twin or into each other. `bt pick` is the tool built for this (direction defaults PRD→HML; `-r` reverses). On conflict: resolve, then `bt pick continue`.
- **Fast-forward the base before branching off it** (`git pull --ff-only` on `main`/`homolog`).
- **Check what already exists first**: the counterpart branch or its PR may already be open (`git branch -a`, `bt pr list`) — reuse and complete, don't duplicate. If the base already contains the ticket's commits (counterpart merged), that leg is done.
- Tests cannot run locally in this repo — the pipeline is the only test oracle.

## Flow

1. Identify the ticket from the current branch (`{TICKET}-{suffix}`) and which twin you're on. Read the repo's CLAUDE.md.
   Completion: you know the ticket id, which twin exists, and what's missing (counterpart / PRs / pipelines).
2. Create or refresh the counterpart from its freshly-pulled base, carry the commits over with `bt pick`, push.
   Completion: counterpart pushed; `git log` on it shows the ticket's commits on top of its base.
3. Create the missing PR(s) — exact flags in [references/gitflow-facts.md](references/gitflow-facts.md); the flags are not optional.
   Completion: one open PR per twin.
4. Watch both pipelines to a terminal state and report.
   Completion: user has PR ids + pipeline verdicts, and any failure has a diagnosis.

## Common mistakes

| Mistake | Reality |
|---|---|
| Force-pushing to fix commit-message prefixes | The branch is pushed and possibly reviewed. Leave history alone. |
| `bt pr create` with ad-hoc flags | Without `--no-push` it prompts to push and dies headless. Use the exact team invocation. |
| Merging homolog into the -hml branch | Twins carry cherry-picks only; merges pollute the PR diff. |
| Branching -hml from main | -hml is based on homolog. Suffix names the base (see references). |
| Declaring done after PR creation | Pipelines are the oracle; the ritual ends at green (or a diagnosed red). |
