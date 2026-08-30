"""Money as a value object.

Amounts are stored as integer minor units (öre / cents). Floats never touch a
price in this codebase - a 0.1 + 0.2 rounding drift on an order total is the
kind of bug that shows up in accounting three months later.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_EXPONENTS = {"SEK": 2, "EUR": 2, "USD": 2, "ISK": 0}


@dataclass(frozen=True, slots=True)
class Money:
    minor_units: int
    currency: str = "SEK"

    def __post_init__(self) -> None:
        if self.currency not in _EXPONENTS:
            raise ValueError(f"unsupported currency: {self.currency}")

    @classmethod
    def from_decimal(cls, amount: Decimal | str | int, currency: str = "SEK") -> Money:
        exp = _EXPONENTS[currency]
        quantum = Decimal(1).scaleb(-exp)
        value = Decimal(str(amount)).quantize(quantum, rounding=ROUND_HALF_UP)
        return cls(int(value.scaleb(exp)), currency)

    def to_decimal(self) -> Decimal:
        return Decimal(self.minor_units).scaleb(-_EXPONENTS[self.currency])

    def _assert_same(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(f"currency mismatch: {self.currency} vs {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._assert_same(other)
        return Money(self.minor_units + other.minor_units, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same(other)
        return Money(self.minor_units - other.minor_units, self.currency)

    def __mul__(self, qty: int) -> Money:
        if not isinstance(qty, int):
            raise TypeError("money can only be multiplied by an integer quantity")
        return Money(self.minor_units * qty, self.currency)

    def apply_rate(self, rate: Decimal) -> Money:
        """Multiply by a rate (VAT, discount) with half-up rounding."""
        value = (Decimal(self.minor_units) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return Money(int(value), self.currency)

    @property
    def is_zero(self) -> bool:
        return self.minor_units == 0

    def __str__(self) -> str:
        return f"{self.to_decimal()} {self.currency}"
