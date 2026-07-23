from src.pricing import round_money


def checkout_total(subtotal):
    if subtotal < 0:
        raise ValueError("subtotal must be non-negative")
    return round_money(subtotal)
