# Acme Size-Gate Policy

Read this file on a size-check failure before any label, comment, source edit, or split decision. This is repository- and provider-specific: inspect the current workflow and repository policy first. The values below preserve the audited policy but must not override newer authoritative configuration.

## Current audited policy

`example-platform` uses `.github/workflows/pr-size.yml`, historically exposed as `PR Size Gate` / `Diff size (excl. generated)`. Its audited hard cap is 1,000 effective LOC with an aim near 400. Effective LOC is additions plus deletions after workflow exclusions; tests are not excluded.

The `size/override` label is an exception and must have one honest rationale explaining why the PR cannot split into independently mergeable changes. Adding the label re-runs the check on the `labeled` event.

## Decision protocol

1. **Idempotent guard:** inspect labels and prior comments. If `size/override` and its rationale already exist, add neither again. The PR is `WAITING` until the newest labeled-event check is explicitly observed terminal-good; an existing override is not proof of `DONE`. **Never infer** the size result from the label, old rationale, unrelated check results, or generic status summaries.
2. **Measure effective LOC:** mirror the current workflow's exact exclusions. Do not trust raw GitHub additions/deletions or a stale regex.
3. **Inspect cohesion:** compare the current diff/stat, ticket, and independently mergeable seams.
4. **Choose exactly one:** cohesive override, or split STOP. Never edit source merely to appease this check.
5. Report the effective LOC and choice every cycle and in the final report.

Audited exclusion recipe (validate against the current workflow before relying on it):

```bash
EXCLUDE='(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock)$|^backend/supabase/migrations/|^frontend/src/components/ui/|^frontend/src/integrations/supabase/types\.ts$|^docs/adr/|^docs/explanation/architecture/adr/'
gh api --paginate "repos/<owner/repo>/pulls/<#>/files?per_page=100" \
  | jq --arg ex "$EXCLUDE" '[ .[] | select(.filename | test($ex) | not) | (.additions + .deletions) ] | add // 0'
```

## Override

Override only a cohesive single feature/fix whose files must move together and whose split would create nonfunctional or non-independently-mergeable intermediate branches.

Add the label once, then one specific rationale stating the change, effective LOC, why it is cohesive, and why named split options would not work:

```bash
gh pr edit <#> --repo <owner/repo> --add-label "size/override"
gh pr comment <#> --repo <owner/repo> --body \
  "**size/override rationale:** <specific cohesive reason>. Effective diff ~<N> LOC using the current workflow exclusions."
```

No boilerplate. If an honest reason cannot be stated, do not override.

## Split STOP

Never override a clearly separable PR or one roughly over **2,000 effective LOC**. STOP that PR's fix path and name concrete independently mergeable seams by scope/ticket/feature—for example API refactor, UI feature, and test harness. The overall sweep remains nonterminal and re-arms for user adjudication.

Surface both override and split decisions; do not bury policy actions in generic CI status.
