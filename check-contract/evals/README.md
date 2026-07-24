# Check-contract evaluation fixtures

`materialize_fixture.py` exclusively invokes the canonical
`exec-ticket/evals/materialize_fixture.py contract-repo` materializer for each
fresh target. It verifies canonical branch, HEAD, and cleanliness before
constructing a sanitized shipped history on the approved base.

The wrapper caches only approved authority bytes and explicitly listed audited
source/test bytes, resets only the newly-created disposable repository, applies
one explicit overlay, and rejects every path or Git status outside
`fixture-manifest.json`. Canonical fixture setup, `.fixture`, worker validation,
caches, and undeclared narrative files never enter the audited history.

Task 1 baseline runners receive only absolute target path(s), the exact neutral
prompt from `evals.json`, and an artifact destination. They receive no skill,
external check-contract implementation plan, eval contract, expected verdict,
or shared skills-tree path. The canonical approval base already tracks the
repository-local ticket context `plan.md`; materialization preserves those
bytes unchanged. That base context is not post-base author narrative and must
contain no scenario, assertion, verdict, or route vocabulary.

Iteration 4 uses assertion contract v2. AB1 is compound-only: it contributes
to `compound_pass`, never `target_b_pass`. Report delivery and mutation scope
are distinct assertions. Iterations 1-3 retain their original assertions and
grades and must not be rewritten.

Treatment runs freeze the installed `check-contract` skill and deterministic
runtime as one reviewed snapshot. The skill starts one runtime session, reads
only runtime-issued packets, supplies the two closed judgment responses, and
follows returned continuation commands. Repository inspection, aggregation,
routing, report publication, retries, and compound A-then-B closure remain
runtime-owned. Trials never patch the frozen snapshot or replace a behavioral
failure.
