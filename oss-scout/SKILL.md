---
name: oss-scout
description: Use when looking for open-source projects to contribute to, asking which repos genuinely need contributors, wanting unclaimed approachable issues that aren't crowded with competing PRs, or hunting for projects in a specific area (systems programming, databases, backend, compilers) to level up in. Also use when resuming or widening a previous contributor search.
---

# oss-scout

Finds under-resourced OSS projects with genuinely unclaimed issues, accumulating coverage across runs instead of re-reading the same first page.

## Core principle

**GitHub caps every search at 1000 results.** Coverage therefore only grows if you partition the query space into drainable slices and remember which are burned. Without a slice ledger, "search again" just re-reads the same top results and reports false progress.

## When to use

- "find me an OSS project to contribute to"
- "what needs contributors in systems programming / databases?"
- "continue the search, show me another batch"
- Wanting issues nobody has claimed — no assignee, zero comments

Not for: picking an issue inside a repo you already contribute to.

## Pipeline

Three stages, run in order. Each is independently resumable.

```bash
scripts/discover.py --budget 4000     # GitHub -> data/pending.jsonl
scripts/classify.py                   # cheap model -> data/corpus.jsonl
scripts/report.py --theme systems database
```

| Stage | Cost | Notes |
|---|---|---|
| `discover` | GitHub quota (the real bottleneck) | Burns unburned slices, applies mechanical health gate |
| `classify` | ~$0.40 per 6k repos | `pi --provider opencode-go --model deepseek-v4-flash` |
| `report` | free | Pure local query — re-theming costs nothing |

Run `--help` on any script for flags.

## Why classification is theme-agnostic

The model emits a fixed domain vocabulary (`systems`, `database`, `compiler`, …) rather than answering "is this systems programming?". Theme filtering is then a local grep, so switching themes re-uses everything already judged instead of paying to re-judge it.

## Data

```
data/corpus.jsonl   append-only, one line per repo judged (the accumulated asset)
data/slices.json    ledger: which slices are burned, which were truncated
data/pending.jsonl  discovered but not yet classified; retried automatically
data/shortlist.md   regenerated per theme
```

## Non-obvious constraints (all learned the hard way)

- **`stars:` silently returns 0 in issue search.** It is not supported and does not error. Slicing uses `created:` date windows instead — every issue has exactly one creation date, so windows are provably exhaustive and subdividable.
- **A slice returning exactly 1000 was truncated**, not complete. It gets split into half-windows and re-queued. Skipping this makes "exhaustive" a lie.
- **Secondary rate limits are burst-based**, not quota-based: `gh api rate_limit` can read 5000/5000 while you are blocked. Search needs ≥3.5s spacing; 2s fails.
- **Repos under 6 months old are the dominant noise source** — 65% of candidates in testing, nearly all new projects that bulk-created issues at launch. The age gate is the cheapest high-yield filter.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Swallowing `gh` errors and returning `None` | Whole languages vanish silently; the run looks successful |
| Piping progress through `tail` | Buffers to the end — you fly blind for the entire run |
| Re-judging repos already in the corpus | Pays again for a verdict you already own |
| Trusting `total_count` as repos examined | It counts *matching issues* on GitHub, not what you fetched |
