# Frontend QA

Read this file before frontend route discovery, browser setup, or browser actions.

## Setup and route authority

Load the `agent-browser` skill before browser use. Establish safe development authentication from project docs/source: test bypass, expected localStorage/cookie session, or the test login flow. Never invent credentials or reuse production auth.

Discover the frontend route from changed files/router configuration first, then home navigation if needed. Never guess or prefer a user-suggested path over router/source evidence.

## Evidence cycle

For every frontend test:

1. Navigate to the authoritative route and wait for `networkidle`.
2. Snapshot to discover interactive elements.
3. Interact using **current refs**.
4. Wait for the resulting load/API work.
5. Re-snapshot; every DOM-changing action invalidates prior refs and evidence.
6. Assert a **fresh post-action** visible state, text, element, and/or current URL against the expected result.

Old matching text is stale evidence. An endless spinner, failed data request, unavailable browser, or missing fixture is `SKIP/INCONCLUSIVE`, never a product PASS. Capture a screenshot and fresh snapshot when diagnosing a visible failure.

If loading persists, wait and re-snapshot. If an element is offscreen, scroll and re-snapshot. Use a JavaScript Radix fallback only after an **ordinary click** demonstrably failed to transition the component; then wait, re-snapshot, and verify the state transition.

## Retry synchronization

After every frontend source edit, wait for HMR **and network idle** before the next attempt. This applies after the first edit as well as later edits. Acquire fresh refs after reload; never replay an invalidated ref.
