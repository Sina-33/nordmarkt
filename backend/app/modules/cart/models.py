from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class Cart(UUIDPrimaryKey, Timestamped, Base):
    """A cart belongs either to a signed-in user or to an anonymous token.

    Guest carts are merged into the user's cart on sign-in rather than
    discarded - losing a basket at the login wall is a measurable conversion
    leak.
    """

    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None, index=True
    )
    anonymous_token: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="SEK")
    locale: Mapped[str] = mapped_column(String(5), default="sv")
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_open(self) -> bool:
        return self.checked_out_at is None


class CartItem(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_variant"),)

    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"))
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    # Price captured when the item was added, used to detect and surface price
    # drift at checkout instead of silently charging a different amount.
    unit_price_minor_units: Mapped[int] = mapped_column(Integer)

    cart: Mapped[Cart] = relationship(back_populates="items")
