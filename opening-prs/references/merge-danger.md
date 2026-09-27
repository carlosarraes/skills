# Merge danger

Two lines close every reviewer brief. They tell the reviewer whether the full read is needed: a two-way door with a narrow blast radius can be merged on the summary; anything else gets read.

```
## Merge danger

**Door:** two-way
**Blast radius:** <what breaks, and for whom, if this is wrong>
```

## Door

- **two-way**: merging and reverting tomorrow costs nothing. The revert restores the previous behaviour completely, and nothing outside the codebase remembers the change happened. Most code, test, UI, and internal refactor changes.
- **one-way**: something is left behind that a revert does not undo. A migration that rewrites or deletes data, a dropped collection or index, an outbound email, webhook, or message sent to a customer, a billing or payment call, a public API or contract change with external consumers, a secret rotation, or data written in a new shape that old code cannot read.

Decide from the diff, not from the size. A one-line change that sends an email is one-way; a thousand-line UI refactor is two-way. When in doubt, one-way: a reviewer reading a two-way PR too carefully costs minutes, while skipping a one-way PR costs whatever the revert cannot recover.

## Blast radius

One phrase naming what breaks, and for whom, if the change is wrong. Name the surface and the people, not the files: "buyers' portal totals on ramped quotes", not "pricing.py". For a non-trivial backend change, run `blast-radius` first and phrase its one safety fact's failure case. Never write a deferral (`TBD`, `n/a`, `-`) and never leave a placeholder; if the blast radius is genuinely nothing outside the diff's own tests, say so in words: "none outside the changed test suite".

## Examples

A display fix, reverted cleanly:

```
**Door:** two-way
**Blast radius:** buyers and reps reading a ramped quote's totals in the portal, PDF and workspace
```

A migration that rewrites stored records:

```
**Door:** one-way
**Blast radius:** every organization's stored quotes: a wrong backfill rewrites their totals and a revert does not restore the old values
```
