from src.pricing import round_money


class _DiscountCalculation:
    def __init__(self, subtotal, percentage):
        self.subtotal = subtotal
        self.percentage = percentage

    def total(self):
        return round_money(self.subtotal * (1 - self.percentage / 100))


def checkout_total(subtotal):
    if subtotal < 0:
        raise ValueError("subtotal must be non-negative")
    return round_money(subtotal)


def apply_discount(subtotal, percentage):
    if percentage < 0 or percentage > 100:
        raise ValueError("percentage must be between 0 and 100")
    return _DiscountCalculation(subtotal, percentage).total()
