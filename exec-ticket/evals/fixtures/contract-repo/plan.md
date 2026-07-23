# PROJ-123 — Percentage discount at checkout

The design is settled. Add `apply_discount(subtotal, percentage)` to checkout.

Required behavior:

- A zero percentage leaves the subtotal unchanged.
- A percentage from 0 through 100 returns the discounted total rounded to two
  decimal places.
- A percentage below 0 raises `ValueError`.
- A percentage above 100 raises `ValueError`.

Expected approach:

- Keep percentage validation local to `src/checkout.py`.
- Reuse the existing money-rounding helper.
- Add focused behavior tests before implementation.

Non-goals:

- coupon codes or stacking discounts
- persistence, configuration, or feature flags
- runtime dependencies
- a discount class hierarchy or new module
