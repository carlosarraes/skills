def round_money(amount):
    return round(amount, 2)


def validate_percentage(percentage):
    if percentage < 0 or percentage > 100:
        raise ValueError("percentage must be between 0 and 100")
