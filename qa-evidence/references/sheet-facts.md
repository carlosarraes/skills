# QA sheet facts (volatile — re-verify if the team rotates the spreadsheet per quarter)

- Spreadsheet id: `REDACTED_SPREADSHEET_ID` (title `QA-Q326` — quarterly; if the title no longer matches the current quarter, ask the user for the new id and update this file).
- One tab per ticket. In-progress: `PROJ-nnn`. Approved: renamed `PROJ-nnn - aprovado` / `- APROVADO` (spacing/case vary) — always prefix-match.
- `gws` prints `Using keyring backend: keyring` on every call — strip it before parsing JSON.

## Layout (identical on TEMPLATE and every ticket tab)

| Row | Content |
|---|---|
| 2 | `AMBIENTE` \| `TESTADO POR` \| `CARD JIRA` \| `PROTÓTIPO` |
| 3 | values, e.g. `HML` \| `Carlos Arraes` \| `PROJ-817` |
| 5–7 | `LINK EVIDÊNCIA (se houver video)` / `DEV:` / `PM:` |
| **9** | header: `CENÁRIO` \| `RESULTADO ESPERADO` \| `TESTE DEV [DATA]` \| `TESTE PM [DATA]` \| `TESTE TL [DATA]` \| `OBSERVAÇÕES` |
| 10+ | scenario rows (columns A–F) |

Reads return trailing-truncated rows (empty tail cells omitted) — never index blindly into positions 3–5.

## Commands

```bash
# list tabs (always pass fields — the raw get is hundreds of lines of noise)
gws sheets spreadsheets get --params '{"spreadsheetId":"<ID>","fields":"sheets.properties.title"}'

# read a tab (quote tab names in ranges)
gws sheets +read --spreadsheet <ID> --range "'PROJ-817'!A1:F20"

# the one write (all rows composed, single call)
gws sheets spreadsheets values update \
  --params '{"spreadsheetId":"<ID>","range":"'\''PROJ-817'\''!A10:F13","valueInputOption":"USER_ENTERED"}' \
  --json '{"values":[[...],[...]]}'

# create a missing tab
gws sheets spreadsheets batchUpdate --params '{"spreadsheetId":"<ID>"}' \
  --json '{"requests":[{"addSheet":{"properties":{"title":"PROJ-nnn"}}}]}'
```

## Row style — the recipe

Write for the PM: what a user does → what visibly happens. One scenario per row.
- CENÁRIO opens with `Quando ...` (or a bare state description): `Quando o cliente em pending_overage clica em contratar um novo plano`
- RESULTADO ESPERADO opens with `Deve ...` / `Não deve ...`: `Deve abrir o checkout direto na etapa de cartão, em modo excedente`
- TESTE DEV: `Sucesso [03/08]` (literal word + date). Skipped/failed: leave blank, reason in OBSERVAÇÕES.
- Language follows the ticket (PT-BR default; ES tickets get ES).

Real rows from PROJ-780 for register calibration (business language, zero jargon):

| CENÁRIO | RESULTADO ESPERADO |
|---|---|
| Renovação mensal normal de um plano ativo | Enquanto aguarda o pagamento fica "Aguardando pagamento"; ao pagar vira "Pago"; se a cobrança falhar vira "Não pago" — sempre um status válido. |
| Vários avisos de cobrança chegam fora de ordem ou ao mesmo tempo | A assinatura termina sempre num status válido e correto; nenhum status inválido permanece. |
