# Durable Chaos Plan

Read this file before creating, replacing, or displaying a chaos plan.

## Path and overwrite gate

Preserve branch hierarchy exactly:

- when `.notes/` exists: `.notes/<branch-name>/chaos-plan.md`;
- otherwise: `ai_docs/<branch-name>/chaos-plan.md`.

Branches with slashes intentionally create nested directories. In a normal run, create the parent directory and durable plan only after discovery, oracles, and all seven design results exist.

If the target exists, read it and require explicit confirmation before replacement; offer to show a diff between old and proposed content. Earlier “run all,” “reuse,” or “overwrite without asking” language is not consent at this gate. Display the diff when requested and write only after the user explicitly confirms replacement. An existing plan is not implicit authorization to execute it.

Only when the entire run is explicitly a simulation/preview-only/read-only trace with **no execution or mutation** (or carries exact `SIMULATION ONLY`), state the exact target and render the would-be plan/diff/confirmation trace, but **do not write**, mkdir, replace, or otherwise mutate a file. Merely limiting real execution to read-only experiments does not suppress the normal durable plan.

## Required plan shape

```markdown
# Chaos Plan: <branch>

- **Ticket**: <ID> — <title> | no ticket
- **Platform**: linear | jira
- **Date**: <YYYY-MM-DD>
- **Output dir**: .notes | ai_docs
- **Backend URL**: <loopback URL> | not reachable — execution skipped
- **Frontend URL**: <loopback URL> | not reachable — execution skipped
- **Test runner**: <runner> | none — auto-fix disabled

## Steady-state hypotheses
- <surface>: <oracle>

## Experiments
### 1. Input / injection
| ID | Hypothesis | Experiment | Expected resilience | Severity | Blast radius |
|----|------------|------------|---------------------|----------|--------------|

<!-- Repeat all seven categories. Say explicitly when a category is skipped/no experiment in scope. -->

## Notes & warnings
- **Data-mutating experiments**: <IDs/effect/reseed need>
- **Auth bypass**: <IDs and throwaway test credentials>
- **Destructive risk**: <IDs and possible local residue>
- **Unreachable surfaces**: <surface and execution skip>
```

Every experiment includes ID, hypothesis, concrete interaction/payload, expected resilience, severity, and blast radius. Preserve explicit skipped categories instead of deleting empty tables. Identify data-mutating, auth bypass, and destructive risk before selection so consent is informed.

## Display and selection prompt

After the normal durable write, print the plan inline or a viable summary that retains metadata, hypotheses, every category/ID, skips, and warnings. Then ask exactly for one selection class:

- `all`;
- comma-separated IDs;
- one category;
- `abort` — keep the durable plan and execute nothing.

Wait for the post-display answer. Do not reinterpret an earlier instruction as this selection.
