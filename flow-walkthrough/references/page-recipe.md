# Page recipe

One self-contained HTML file. Embed every screenshot as a base64 data URI (build with a small script — read files, emit HTML — never hand-paste base64). Keep the finished file under the host's size limit; 10 full-page PNGs at 1440×900 is typically ~1 MB.

## Structure

```
<title>{Flow name} — passo a passo</title>   (or the user's language)
masthead: eyebrow (project/date) · h1 · 2-3 sentence intro · badge legend
per step:  number chip · h2 title · badge · 1-2 sentence caption · framed screenshot
footnote:  "what to look at" + not-shown states
```

- Steps are numbered because a flow is a real sequence; variants of a step share its number with a suffix (5, 5b).
- Badges only when the flow mixes provenance, with plain labels: "Tela nova" / "Já existia" / "Tela reaproveitada" (translate to the page's language). One legend at the top.
- Frame each screenshot in a light browser-chrome bar (three dots) so screens read as screens.

## Intro register

Three sentences, story-shaped, no jargon. Pattern: *the problem today → what changes for the customer → what this page shows*.

> Hoje, quem deve excedente não consegue cancelar o plano — e continua sendo cobrado. Com a mudança, o cliente sempre consegue cancelar; logo depois, oferecemos uma forma fácil de quitar o que ficou em aberto. As capturas abaixo são do fluxo real funcionando, na ordem em que o cliente vê.

## Caption register

| Dev register (never) | Plain register (always) |
|---|---|
| "cancelPlan() success defers the reload and emits to tab-my-plan" | "Aqui o plano já está cancelado de verdade — pagar nunca é condição para cancelar." |
| "GET /v2/payment-method returns the censored card" | "Mostra o cartão que já está salvo, com os números escondidos." |
| "PIX subs get the degraded single-CTA variant" | "Versão da mesma tela para quem não tem cartão salvo. Fica só um botão." |

## CSS tokens

Light palette on bare `:root`; dark palette twice — under `@media (prefers-color-scheme: dark)` guarded `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. `body` always paints its background from a token. Working token set (light → dark):

```
--ground #F5F7FB → #121624   --card #FFFFFF → #1B2133   --ink #1A2340 → #E7EAF4
--slate #5C6680 → #99A2BC    --line #DDE3F0 → #2C3550   --accent #2447D6 → #7C97F5
badge pairs: new (amber), existing (accent), reuse (green) — each with a -soft ground
```

Layout: single column, max-width ~1060px; `img { display:block; width:100%; height:auto; }`; caption `max-width: 72ch`.

## Hosting

- snapdoc: `snapdoc publish page.html --title "..."` (passcode comes from the environment). To revise without changing the link: `--update <id>`. Note the TTL it prints.
- No snapdoc: use the platform's artifact hosting the same way — republish the same file to keep the URL.
