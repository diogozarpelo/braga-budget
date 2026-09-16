from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_decimal(value):
    text = value.strip()

    if not text:
        raise InvalidOperation

    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    return Decimal(text)


def money_to_cents(value):
    amount = parse_decimal(value)

    return int(
        (amount * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
