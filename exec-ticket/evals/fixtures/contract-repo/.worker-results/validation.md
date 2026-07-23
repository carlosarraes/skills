# Validation worker result

The approved contract expected local validation in `src/checkout.py`, but a
shared validator landed after the contract base:

- Helper: `src/pricing.py:5` — `validate_percentage`
- Focused evidence: `python -m unittest tests.test_pricing`
- Result: `Ran 2 tests ... OK`
- Proposed path: import and call the helper from `src.checkout.apply_discount`
  instead of duplicating its boundary checks.

The worker did not edit the execution ledger.
