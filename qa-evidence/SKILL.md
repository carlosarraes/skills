---
name: qa-evidence
description: "Use after a QA pass on a acme ticket (PROJ-*, PROJ-*, etc.) when the results must land in the team QA spreadsheet — the user says 'update the sheet', 'fill the PROJ-nnn tab', 'preencher a planilha', 'fill the cenários', 'update the QA sheet with the tests we did', or a /qa-ticket run in homolog just finished and its evidence needs recording. Uses the gws CLI."
---

# QA Evidence

Record an executed QA run in the team QA sheet: the ticket's tab gets one row per scenario, written the way the PM and tech lead expect to read it.

## Done means

The ticket's tab has, from row 10 down, one row per scenario: CENÁRIO + RESULTADO ESPERADO for every scenario in the QA run, and TESTE DEV filled as the literal word `Sucesso [DD/MM]` for each test that actually passed. Report back the tab name and rows written.

## Hard constraints

- **Only evidence.** Rows come from the actual QA run being recorded. A test that was skipped or failed is never marked `Sucesso` — leave its TESTE DEV blank (optionally note why in OBSERVAÇÕES). Never invent scenarios.
- **Never touch TESTE PM / TESTE TL** (columns D–E) — those belong to the PM and tech lead.
- **One atomic write.** Compose all rows, write once with `values update` to an explicit `'PROJ-nnn'!A10:F...` range. Never use `+append` without `--range` (it targets cell A1 of the FIRST sheet — the TEMPLATE). Never re-send rows because a read-back looks stale; trust the update response.
- The pass marker is the literal word `Sucesso` — not PASS, not OK, not ✅.

## Flow

1. Locate the tab: list tabs and match by ticket-id **prefix** (approved tabs get renamed like `PROJ-761 - APROVADO`, spacing varies). Sheet id, layout, and gws commands: [references/sheet-facts.md](references/sheet-facts.md).
   Completion: you know the exact tab name, or that none exists.
2. No tab? Create one from the TEMPLATE structure (addSheet via batchUpdate, then fill the header block rows 2–3).
3. Read the tab first (rows 1–20): confirm the header row is at row 9 and check for existing scenario rows — append below them, don't overwrite.
4. Write the rows in the register the sheet uses — brief, non-technical, in the ticket's language (PT-BR default). Style recipe and real examples in [references/sheet-facts.md](references/sheet-facts.md).
5. Report: tab, range written, row count, anything left blank and why.

## Common mistakes

| Mistake | Reality |
|---|---|
| `PASS [03/08]` / `OK [03/08]` | The team reads `Sucesso [03/08]`. Literal word, dated. |
| Bare `+append` | Defaults to A1 of the first sheet = the TEMPLATE tab. Always an explicit quoted range. |
| Re-writing rows after an unconvincing read-back | Duplicates the table on the real API. Write once. |
| Exact-match tab lookup | Approved tabs are renamed (`- aprovado` suffix, case/spacing vary). Prefix-match. |
| Technical register ("endpoint retornou 400…" as CENÁRIO) | CENÁRIO/RESULTADO are for non-devs: user action → visible outcome. Technical detail goes in OBSERVAÇÕES. |
