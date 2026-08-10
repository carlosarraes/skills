# Dev notes for the fixture flow (deliberately dev-heavy — the eval must translate these)

Flow: "excluir conta" (delete account), 3 screens, shots already captured in this folder.

1. `01-inicio.png` — /conta/configuracoes renders `account-settings.component` with the `DeleteAccountButton`; clicking it dispatches `openDeleteModal()`. EXISTING screen, unchanged by this ticket.
2. `02-confirmacao.png` — NEW modal `delete-account-confirm-modal` (ticket PROJ-999). Calls `GET /v2/account/blockers/` on open; if the response has `pending_docs > 0` the primary CTA is disabled and a tooltip explains. Primary CTA `POST /v2/account/delete/`, secondary dismisses.
3. `03-final.png` — success state; `logoutAndRedirect('/goodbye')` fires after the 200.

Not capturable live: the `pending_docs > 0` blocked variant (no fixture reaches it) and the 500 error toast.
