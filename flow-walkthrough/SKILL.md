---
name: flow-walkthrough
description: Use when a working UI flow should become a step-by-step visual walkthrough — real screenshots of every screen on one hosted page, captioned so tech and product people can both read it (design critique, product review, feature demo).
---

# Flow Walkthrough

Turn a working UI flow into one hosted page: every screen the user sees, in order, each with a number, a real screenshot, and a caption in plain register.

## Done means

A hosted link (or local file when the user declines hosting) where every screen of the flow appears in the order the user sees it — variants included — each numbered, captioned in plain register, and badged when the flow mixes new, unchanged, and reused screens; plus a "not shown" note for any state that could not be captured live. Report the link and the not-shown list.

## Hard constraints

- **Real screens only.** Drive the actual app and screenshot what renders. A state you cannot reach live (a card decline, a rate limit) goes in the not-shown note — never faked, cropped-in, or mocked up.
- **Plain register, always.** A caption is one or two sentences a product person reads cold: what the user did, what they see. No routes, component names, endpoints, ticket numbers, or code words. Technical detail that must survive goes in one footnote at the end, never in captions.
- **One self-contained page.** Images embedded as data URIs, no external requests — it must render wherever it is hosted.
- **Fixed viewport** for every shot (default 1440×900) so screens line up as a set.

## Flow

1. Map the walkthrough: entry point, each screen in user order, every variant worth its own shot (with vs without a saved card; empty vs filled), and the end state. Completion: an ordered shot list where each entry names the state that must be visible in it.
2. Make every listed state reachable — data, auth, feature setup. A step that consumes its fixture (a modal that appears only once per account) needs one fixture per capture attempt; plan that before driving. Completion: every listed shot has a named fixture or account that produces it.
3. Drive the flow with agent-browser at the fixed viewport; let each screen settle before shooting. Completion: every entry on the shot list has an image file.
4. Read each image back. Retake anything blank, half-loaded, or obscured (a toast that tells the flow's story may stay). Completion: every file visually shows its listed state.
5. Build the page from [references/page-recipe.md](references/page-recipe.md): a three-sentence intro that tells the flow's story in plain register, numbered steps, badges only when new/unchanged/reused screens mix, the not-shown footnote.
6. Host it — snapdoc when available (update the existing artifact id to keep a stable link), otherwise the platform's artifact hosting — and report the link plus the not-shown list.

## Common mistakes

| Mistake | Reality |
|---|---|
| Caption says "the modal calls the pending-summary endpoint" | Product people stop reading. Say "the app checks if there's anything left to pay". |
| Screenshot taken while the page is still loading | Read every image back before publishing. Retake; don't hope. |
| One fixture for a one-shot state | The moment is gone after the first attempt. One fixture per attempt. |
| Skipping variant screens | The degraded or alternate version of a screen is usually what design most wants to critique. |
| Faking an unreachable state | The walkthrough's value is that it is real. List it as not shown instead. |
