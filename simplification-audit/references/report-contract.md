# Report contract

## Canonical ledger

Keep the canonical working ledger outside the repository. It records the
subsystem inventory, confirmed opportunities, explicit skips, cross-cutting
patterns, rejected/duplicate/superseded candidates, final priorities and
dependencies, and the audit log.

## Subsystem row

Each row contains: stable ID, descriptive name, exact ownership boundary, key
files, public interfaces/callers/tests, status, review evidence, and terminal
rationale. Every row terminates as `recommend` or `skip`.

## Finding record

Each candidate records: Verdict; Evidence with exact file-and-line references;
Current complexity or invalid states; Proposed representation and why it is
simpler; Smallest credible implementation scope including affected files and
interfaces; Regression risks and migration concerns; existing and additional
Validation; and Confidence. Add its authoritative subsystem, materiality,
priority, dependencies, and candidate history (`accepted`, `rejected`,
`duplicate`, or `superseded`) with the decision rationale.

## Final report

Render these nine sections in order:

1. Scope, repository revision, and non-mutation proof.
2. Coverage summary.
3. Coverage matrix.
4. Prioritized recommendations.
5. Dependency order and best first implementation slices.
6. Explicit skips.
7. Rejected, duplicate, and superseded candidates.
8. Cross-cutting patterns.
9. Audit-the-audit results and audit log.

## Completion check

Require an exhaustive matrix with a terminal status for every subsystem row,
complete accepted findings, recorded rejections, and deduplication. Confirm
priorities respect dependencies, all five audit-the-audit results are recorded,
and final `git status --short` matches the baseline exactly.
