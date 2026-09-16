from decimal import InvalidOperation

import pytest

from app.utils.parsing import money_to_cents, parse_decimal
from app.utils.text import (
    escape_like,
    normalize_comparison_text,
    phone_digits,
)


def test_parse_decimal_brazilian_format():
    assert parse_decimal("1.234,56") == parse_decimal("1234.56")


def test_parse_decimal_integer():
    assert str(parse_decimal("150")) == "150"


def test_parse_decimal_rejects_empty_value():
    with pytest.raises(InvalidOperation):
        parse_decimal("   ")


def test_money_to_cents():
    assert money_to_cents("1.234,56") == 123456


def test_money_to_cents_rounds_half_up():
    assert money_to_cents("10,005") == 1001


def test_escape_like():
    assert escape_like(r"10%_teste") == r"10\%\_teste"


def test_normalize_comparison_text():
    assert (
        normalize_comparison_text("  Cliente   TESTE  ")
        == "cliente teste"
    )


def test_phone_digits():
    assert phone_digits("(14) 99999-9999") == "14999999999"
