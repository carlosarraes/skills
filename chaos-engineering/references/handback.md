# Complete Report and Local Hand-back

Read this file before the final report or hand-back.

## Inline report

Print the report in chat; the durable artifact is `chaos-plan.md`, not a second report file. Include:

```markdown
# Chaos Report: <ticket> — <title>
**Branch**: <branch>
**Date**: <date>
**Summary**: X resilient, Y fixed, Z violated/failed, I inconclusive, S skipped

## Per-experiment outcomes
| ID | Category | Hypothesis | Expected | Observed | Outcome | Severity |

## Fixes applied
| Finding | File:line | Change | Commit |

## Skipped / failed
- <ID>: <reason, attempts, follow-up>

## Feature resilience: **yes / partial / no**
<what survives and what remains>

## Hand-back
- Review: `git log --oneline <base>..HEAD`
- Re-run: `/chaos-engineering` and select an ID
- Publication remains the user's decision
```

Show **every selected experiment** and every planned-but-unselected, unreachable, or category-skipped experiment. Preserve resilient, fixed, failed, inconclusive, and skipped outcomes; include expected versus observed evidence, all three failed attempts where applicable, each fix's file/line/commit, and scope-boundary follow-ups.

The overall verdict is exactly **yes / partial / no**:

- **yes** only when the selected evidence establishes resilience and no material failure or inconclusive selected case remains;
- **partial** when at least one meaningful surface is resilient or fixed and at least one material selected finding remains failed or inconclusive;
- **no** only when no meaningful resilience remains or the core feature is broadly unsafe.

Do not collapse mixed evidence to `no` merely because one selected finding failed. State which surfaces support the verdict.

Report unknown-platform/ticket-provider degradation, no-test remediation stop, unreachable surfaces, credential skips, and local DB contamination. Recommend `/seed-data` when data-mutating experiments may have left residue.

## Hand-back boundary

The branch remains checked out with the number of new local commits. Never push, force-push, open a PR, merge, amend, or rewrite history. The user decides publication.

Recommend `/clean-up` when repairs were large or the cumulative diff merits a senior pass. Mention `/qa-ticket` when runtime happy-path evidence or a test baseline is still missing. In the router-qualified whole-run simulation mode, describe this exact report and boundary without writing files or performing git/publication actions.
