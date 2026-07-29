# Execution Ledger

## D1 — 2026-07-23T13:03:00Z — fixture-parent

- Affected clauses: R2, S1, K-ABSTRACTIONS
- Discovered fact: `src/pricing.py:5` now provides internal `_validate_percentage`.
- Actual approach: Reuse internal `_validate_percentage` from `src.checkout.apply_discount`.
- Reason for proceeding: B1-B4, C1-C2, I1-I2, and the risk envelope remain unchanged.
- Alternatives considered: Duplicate local validation as predicted; rejected because the shared helper now exists.
- Risk delta: None; one existing tested boundary function replaces duplicate lines.
- Verification evidence: `src/pricing.py:5` plus replay probe Q1 observed 0 and 100 accepted and -1 and 101 raising `ValueError` before the affected implementation commit.
- Replay probe: `{"kind":"python-call-v1","module":"src.pricing","callable":"_validate_percentage","cases":[{"args":[0],"expect":"returns"},{"args":[100],"expect":"returns"},{"args":[-1],"expect":"raises","exception":"ValueError"},{"args":[101],"expect":"raises","exception":"ValueError"}]}`
