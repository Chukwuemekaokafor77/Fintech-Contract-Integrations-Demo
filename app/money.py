from decimal import Decimal, ROUND_HALF_UP


MONEY_SCALE = Decimal("0.01")
RATE_SCALE = Decimal("0.000000")


def q(amount: Decimal) -> Decimal:

    return amount.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def q_rate(rate: Decimal) -> Decimal:
    return rate.quantize(RATE_SCALE, rounding=ROUND_HALF_UP)
