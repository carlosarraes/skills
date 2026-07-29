from src.pricing import _validate_percentage, round_money


def checkout_total(subtotal):
    if subtotal < 0:
        raise ValueError("subtotal must be non-negative")
    return round_money(subtotal)


def apply_discount(subtotal, percentage):
    percentage = min(percentage, 100)
    _validate_percentage(percentage)
    return round_money(subtotal * (1 - percentage / 100))
