# Change Contract: PROJ-123 Percentage discount at checkout

Contract version: 1
Ticket: PROJ-123
Branch: feature/proj-123
Base commit: SET_BY_FIXTURE_SETUP
Created: 2026-07-23T12:00:00Z

## Outcome

Checkout can apply a validated percentage discount without adding new structure.

## Required behaviors

- B1: A zero percentage leaves the subtotal unchanged.
- B2: A percentage from 0 through 100 returns the discounted total rounded to two decimal places.
- B3: A percentage below 0 raises `ValueError`.
- B4: A percentage above 100 raises `ValueError`.

## Explicit non-goals

- N1: Coupon codes or stacking discounts.
- N2: Persistence, configuration, or feature flags.
- N3: Runtime dependencies.
- N4: A discount class hierarchy or new module.

## Invariants and risk boundaries

- I1: Existing checkout subtotal validation and rounding remain unchanged.
- I2: User-visible percentage semantics reject values outside 0 through 100.

## Expected public contracts and side effects

- C1: Add `src.checkout.apply_discount(subtotal, percentage)`.
- C2: No persisted state or external side effects.

## Reuse evidence

- R1: `src/pricing.py:1` — reuse `round_money` for the result.
- R2: repository search found no percentage validator at the contract base, so use a few local lines in `src/checkout.py`.
- R3: `src/checkout.py:4` — extend the existing checkout orchestration module.

## Expected change surface

- `src/checkout.py` — validate the percentage and calculate the discounted total.
- `tests/test_checkout.py` — pin B1 through B4.

## Complexity budget

- New modules: 0
- New runtime dependencies: 0
- New abstractions: 0
- New configuration: 0
- New public interfaces: 1 (`apply_discount`)

## Acceptance evidence

- B1 -> focused unit test for zero percent.
- B2 -> focused unit tests for valid percentages and rounding.
- B3 -> focused unit test for a negative percentage.
- B4 -> focused unit test for a percentage above 100.

## Unresolved decisions

- None
