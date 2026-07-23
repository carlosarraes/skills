from decimal import Decimal


def calculate_percentage_discount(
    subtotal: Decimal,
    percentage: Decimal,
) -> Decimal:
    """Return the rounded discount for an existing percentage promotion."""
    return (subtotal * percentage / Decimal("100")).quantize(Decimal("0.01"))
