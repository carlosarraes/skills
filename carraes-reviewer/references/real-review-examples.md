# Real review examples — Carlos Arraes (Mondrio-App/mondrio-platform)

Mined verbatim from 129 review comments across 43 teammate PRs (2026-06-30 → 2026-07-10). Do not paraphrase these when adapting the voice — they are the ground truth.

## Review-body openers (the summary comment on a review)

- **[CHANGES_REQUESTED]** I found a few issues that need attention before this fully satisfies MON-1386.
- **[CHANGES_REQUESTED]** Review findings for MON-1387. The rate-card handoff is mostly in place, but a few paths need attention before merge.
- **[CHANGES_REQUESTED]** Review found a CI-blocking unused variable and hard-cap behavior that does not match MON-1369 acceptance criteria.
- **[APPROVED]** Overall verdict: correct (no blocking issues).
- **[CHANGES_REQUESTED]** I found a few issues that keep MON-740 from being fully enforced in the normal action execution path and allow invalid version/feature scopes.
- **[CHANGES_REQUESTED]** Review findings for PR #1309. The implementation needs attention before merge.
- **[CHANGES_REQUESTED]** Code review found blocking autosave correctness issues that should be addressed before merge.
- **[CHANGES_REQUESTED]** I found a few blocking/actionable issues in the autosave slice: pending autosaves can race explicit Save, ETag concurrency is not wired even though the endpoint supports it, and autosave bypasses explicit-save validation.
- **[CHANGES_REQUESTED]** Review verdict: needs attention.
- **[CHANGES_REQUESTED]** Found two ticket-compliance gaps in the added test suite that should be addressed before merging.
- **[CHANGES_REQUESTED]** Blocking issue found: the status filter is applied to order MatchRecords, but MON-1500's pooling bug is caused by suggested company cluster membership.
- **[CHANGES_REQUESTED]** The Membrane-driven catalog behavior is mostly in place, but MON-1637 also requires updating the connector promotion docs, and the new conditional hook behavior should have regression coverage per the frontend guide.

## Inline findings — ticket-compliance gaps (his signature move)

- `frontend/src/pages/PriceManager.tsx`:827 — After removing an override, this switches the selector to the currency-default target instead of keeping the removed rate-card target selected. MON-1386 asks for the selected rate card to fall back to the currency default, and the fallback hint only renders for a rate-card target, so the required fallback display is skipped after removal.

- `frontend/src/lib/__tests__/overage-targets.test.ts`:409 — MON-1386 requires coverage for fallback display after removal, but these added tests only exercise the pure helper. Please add a component/regression test that clicks Remove override and verifies the rate-card target shows inherited-default fallback copy afterward; that would catch the selection behavior issue in the page.

- `frontend/src/components/features/SKUFeatureConfigDialog.tsx`:1224 — MON-1369 requires the maximum quantity input to show when the effective choice enforces a hard cap, but this only renders for an explicit `Enforce hard cap`. If the feature default has `hasHardCap: true` and the SKU remains `Inherit feature default`, the effective state enforces a cap while the input is hidden.

- `frontend/src/components/features/SKUFeatureConfigDialog.tsx`:768 — MON-1369 says to keep validation that an explicit hard cap requires a maximum quantity, but this payload can persist `{ hasHardCap: true }` when the user selects `Enforce hard cap` and leaves the quantity blank. The save should reject `hardCapChoice === "enforce"` when `validatedMaxQty` is `undefined`.

- `backend/tests/integration/personas/test_ai_action_execute.py`:493 — [P2] MON-1656 explicitly requires an integration test for the preview→apply happy path, but this added integration coverage only proves `regenerate_section` is exposed as async and refused by `/actions/execute`. Existing router tests mock preview and apply independently, so they do not prove the AI-bar async contract can drive the real token-returning preview flow into apply; please add coverage that exercises preview creation and then applies the returned token.

- `frontend/src/components/features/SKUFeatureConfigDialog.tsx`:1131 — The new rate-card branch hides the inline overage editor, but the dialog can still be saved for other metered settings and that save path does not preserve `metered_config.overage_price_refs`. `usePriceLists` currently maps only legacy `overagePriceId(s)` and serializes only those fields, so saving this dialog after configuring rate-card overages in Price Manager can erase the refs MON-1387 says must remain the single save surface. Please preserve/round-trip refs or ensure this dialog does not write overage config for rate-card SKUs.

## Inline findings — concurrency / races / scoping

- `frontend/src/components/features/SKUFeatureConfigDialog.tsx`:1144 — The CTA only renders when `propositionId && skuId`, but `SKUFeatureTable` still instantiates this dialog without either prop, including from `deal-desk/SKUFeatureManager` where both route params are available. In that path, a rate-card SKU now loses the inline editor and shows only explanatory text with no deep link, missing MON-1387’s “clear CTA” acceptance criterion. Plumb the IDs through `SKUFeatureTable` as well.

- `backend/src/ai_assistant/routers/chat.py`:517 — This only injects `version_id` when `ActionExecuteRequest.version_id` is present, but the existing frontend action execution path builds the execute request without `versionId` even though it has `currentVersionId`. In the SKU Manager apply flow, create actions still reach the create handlers with `version_uuid=None`, bypassing the draft-version guard and creating unversioned objects. The execute request needs to carry the current/new version id from the frontend, including the newly-created version id for `target === "new_version"`.

- `backend/src/proposition_manager/ai_actions.py`:611 — This verifies that each added feature exists in the same org, but MON-740 also called out wrong-proposition feature links. In an org with multiple propositions, a feature from proposition B can still be added to a SKU under proposition A because the query does not constrain `ObjectDocument.proposition_id` to the SKU proposition (`doc.proposition_id or doc.parent_id`). This should mirror the proposition check used by `_handle_update_sku_feature_display`.

- `backend/src/proposition_manager/ai_actions.py`:351 — The handler only validates UUID syntax before passing `version_id` to `_service.create`; the service draft guard looks up by id without tenant/proposition filtering and allows missing versions through. A direct caller can send a nonexistent version id or a draft version id from another org/proposition, creating objects in the current org with a corrupt foreign/unresolvable `version_id`. Resolve the version through the org-scoped version service and ensure it belongs to the same proposition/SKU before creating.

- `frontend/src/hooks/useSKUFeatureConfigAutosave.ts`:146 — The debounced callback captures the `performWrite` from the render that called `markDirty()`. In handlers like custom name / quantity, `setState(...)` runs immediately before `markDirty()`, so the scheduled write can build its payload from the previous value and mark "Saved" while persisting stale data. Use a latest-value ref or schedule after state has committed so the final paused edit is what gets autosaved.

- `frontend/src/hooks/useSKUFeatureConfigAutosave.ts`:107 — Overlapping autosave requests are not ordered. If request A is in flight, the user edits again, and request B completes before A, the older A can finish last and overwrite the newer payload through the same full `PUT /api/skus/:sku_id/features` path. Add a request sequence/abort or wire If-Match so stale responses cannot mark the dialog saved or persist over newer edits.

## Inline findings — CI / build gates

- `frontend/src/components/features/SKUFeatureConfigDialog.tsx`:361 — `effectiveHardCapEnforced` is introduced but never read. This repo has `noUnusedLocals: true` in `frontend/tsconfig.app.json` and Biome `noUnusedVariables: error`, so frontend type-check/lint will fail for this PR. Either use this value for the hard-cap visibility logic or remove it.

- `backend/src/ai/services/context_assembler.py`:48 — [P1] `_kb_cache: TTLCache[str, list] = TTLCache(...)` introduces strict type-check failures: `list` is missing a type argument and the constructor inference is not assignable to the declared cache type. Since `uv run pyright` is a required backend gate, this will block the PR until the cache value type and constructor are explicitly typed, e.g. as a cache of `KBArticle` lists.

- `backend/tests/unit/ai/test_context_assembler.py`:383 — [P1] This local `import html` is unused, and both Ruff (`F401`) and Pyright (`reportUnusedImport`) flag it. The backend lint/type-check gates will fail until this import is removed.


---

# Zapsign / Bitbucket corpus (Portuguese-English, casual register)

Mined verbatim via `bt pr review-history` (30 comments, `zapsign/api`, 2026). Same reviewer, different register: bilingual PT-BR/EN and far more conversational than the Mondrio corpus. Substance is the same — regressions, N+1s, swallowed errors, type/signature mismatches, validation bypasses, defensive nil-handling, observability/support-friendliness — but the tone is a teammate thinking out loud, often hedged with "might be intentional" / "is this intended?".

## Reviewing others — substance findings

- `backoffice/modules/payments/serializers.py:75` — This will cause an N+1 query on the pricing-options list. Since payment_methods is an M2M, please `prefetch_related('payment_methods')` in the list queryset.
- `backoffice/.../priced_entity_validator.py:160` — This only rejects `[pix_id]`. Inputs like `[pix_id, pix_id]` or `[pix_id, 999999]` can still resolve to only PIX after `filter(id__in=...)`, so this rule is bypassable.
- `.../pricing_option_update_service.py:34` — Unknown payment method IDs are ignored here. If none of them exist, `.set(payment_methods)` clears the current payment methods instead of returning a validation error.
- `api/services/events/handlers/doc_signed_handler.py:61` — Here, `notify()` returns `False` when it fails… we are ignoring that and, if it fails, we will still count as a success, i dont think thats intended?
- `api/services/events/handlers/doc_signed_handler.py:52` — This function signature says it is going to return a Dict[str, bool] but it only returns a bool? I saw that we ignore the return of this function, but still… i think its good to fix this
- `.../create_plan_subscription.py:107` — The previous facade persisted newly created cards via `_persist_saved_card()`… so enabling this refactor stops cards created during plan subscription from being saved for later reuse. Just letting you know theres a regression here (might be intentional).
- `.../pagarme_v5_facade.py:321` — I would raise here if `raw_status` is `None`, so we can be super clear on whats happening.
- `.../pagarme_v5_facade.py:150` — In here, you are just logging the keys, no? That isnt helpful for support.
- `api/services/events/event_handler.py:57` — Hmm this checks for `truora_client` but not `truora_client_id`… meanwhile `_is_truora_notifier_enabled` checks both, shouldnt we check both here too?
- `utils/webhook/webhook_utils.py:50` — Is this intended? we wont persist it anymore, WebhookLog entries wont be linked to their endpoint

## Portuguese-BR register (same person, casual)

- `docs/v2/dtos/create_document_dto.py:46` — Dessa forma aqui, qnd o lang não for enviado, todo doc vai ser pt-br… o behavior atual é "Se não tem lang, o fallback é `doc.company.lang`", com essa mudança nunca teremos esse fallback, melhor deixar `None` msm para ter o fallback de volta.
- `docs/v2/views/documents_view.py:47` — Hmmm eu moveria isso aqui para dentro do `try`… por mais que vc esteja cobrindo tudo para montar o DTO certinho, se no futuro tiver alguma alteração e a pessoa não cobrir tudo, vai só levar 500 na cara
- `docs/v2/dtos/create_signer_dto.py:7` — Acho que teve uma regressão aqui, talvez seja intencional, mas antes o signer chegava no `create_doc()` com `name` e `auth_mode` vazios

## Author-reply register (his own PRs, defending/explaining decisions)

- Confirmed with pedro, this is the expected behavior
- It's per-instance (`cached_property`), so it dies with the request/task… no shared cache, nothing to invalidate. It'd only go stale if we re-read the active item after mutating items on the same instance, and no flow does that.
- Truncation… afaik we have limits on datadog, this gets the first 1k characters which is what is usually relevant to us
