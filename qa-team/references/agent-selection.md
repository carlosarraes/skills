# Base and Reviewer Selection

Read this file before selecting scope or reviewer roles.

## Select one base

An explicit base argument always wins. Otherwise probe with `git rev-parse --verify` in fixed order and stop at the first match:

1. `origin/develop`
2. `origin/main`
3. `origin/master`

Gather all review material from the same selected base:

```bash
git diff <base>...HEAD --name-only
git diff <base>...HEAD
git log <base>...HEAD --oneline
```

The first command supplies the file list, the second the full triple-dot diff, and the third the commit log. Never substitute a two-dot diff or mix bases. An **empty diff** stops the workflow: report no changes relative to the base, make no reviewer calls, and write no `QAREPORT.md`.

## Classify changed files

| Changed surface | Specialist domains |
|---|---|
| migrations, DDL, `*.sql` schema | database, reliability, compatibility |
| backend views/API/serializers/routes | security, reliability, performance, data-integrity |
| background tasks, cron, queues | reliability, performance, data-integrity |
| frontend `*.tsx`/`*.ts` | frontend, security, performance, copy |
| raw SQL or ORM query behavior | database, performance, data-integrity |
| deploy/runtime/infra config | compatibility, reliability |
| dependency manifests | security, compatibility |
| public API/SDK contract | compatibility, frontend, security, copy |
| user-facing strings | copy |
| CI workflows | security |

Deduplicate the selected domains. Validate repository-specific paths and technologies rather than stretching this table to unrelated files.

## Enforce reviewer topology

Always deploy **at least four specialists**. When direct classification yields fewer, add missing domains in this exact fallback order: `reliability, security, performance, compatibility`; stop once four specialists are selected.

Always add:

- `generalist-a`: fresh-eyes senior-engineer correctness and maintainability;
- `generalist-b`: adversarial QA breakability and production failure modes.

The generalists are distinct and do not count toward the four-specialist floor. A docs/copy-only change therefore selects `copy`, then `reliability`, `security`, `performance`, plus both generalists—six reviewers total.
