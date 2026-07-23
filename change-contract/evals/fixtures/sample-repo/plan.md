# Settled design: optional launch discount

Add an optional percentage discount to checkout totals.

Decisions:

- `checkout_total` accepts `discount_percentage: Decimal | None = None`.
- A missing discount preserves the current total.
- A provided discount uses the repository's existing percentage calculation.
- Percentages below 0 or above 100 raise `ValueError`.
- This ticket does not add promotion persistence, coupon codes, stacking,
  configuration, feature flags, new dependencies, or a discount class hierarchy.
- Tests must cover no discount, a valid discount, and both invalid boundaries.
