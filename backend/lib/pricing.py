"""Cent-exact invoice discount allocation, with deterministic remainder handling."""
from decimal import Decimal, ROUND_HALF_UP


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def allocate_discount(gross_amounts, discount):
    total = sum(gross_amounts)
    if discount < 0 or discount > total:
        raise ValueError("Potongan tidak boleh melebihi total nota")
    if not total:
        return [0] * len(gross_amounts)
    amounts = [discount * amount // total for amount in gross_amounts]
    order = sorted(range(len(amounts)), key=lambda i: (-(discount * gross_amounts[i] % total), i))
    for i in order[:discount - sum(amounts)]:
        amounts[i] += 1
    return amounts
