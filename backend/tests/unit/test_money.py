from decimal import Decimal

import pytest

from app.core.money import Money


def test_decimal_round_trip_is_exact() -> None:
    assert Money.from_decimal("1299.99").minor_units == 129_999
    assert Money(129_999).to_decimal() == Decimal("1299.99")


def test_half_up_rounding_matches_invoicing_rules() -> None:
    # Banker's rounding would give 1299.98 here, which disagrees with how a
    # Swedish invoice is expected to round.
    assert Money.from_decimal("1299.985").minor_units == 129_999


def test_arithmetic_stays_in_integers() -> None:
    unit = Money.from_decimal("0.1")
    assert (unit * 3).to_decimal() == Decimal("0.30")


def test_vat_extraction_from_gross_price() -> None:
    gross = Money.from_decimal("1250.00")
    vat = gross.apply_rate(Decimal("0.25") / Decimal("1.25"))
    assert vat.to_decimal() == Decimal("250.00")


def test_currency_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        Money(100, "SEK") + Money(100, "EUR")


def test_multiplying_by_float_is_rejected() -> None:
    with pytest.raises(TypeError):
        Money(100) * 1.5  # type: ignore[operator]
