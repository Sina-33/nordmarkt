from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class StockItem(UUIDPrimaryKey, Timestamped, Base):
    """Available-to-promise stock for one variant in one warehouse.

    ``on_hand`` is physical, ``reserved`` is claimed by open checkouts. Sellable
    is the difference and is enforced by a check constraint, so even a buggy
    service cannot oversell - the database refuses the write.
    """

    __tablename__ = "stock_items"
    __table_args__ = (
        Index("uq_stock_variant_warehouse", "variant_id", "warehouse_code", unique=True),
        CheckConstraint("on_hand >= 0", name="on_hand_non_negative"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("reserved <= on_hand", name="reserved_within_on_hand"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True
    )
    warehouse_code: Mapped[str] = mapped_column(String(16), default="SE-STO")
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)

    @property
    def sellable(self) -> int:
        return self.on_hand - self.reserved


class StockReservation(UUIDPrimaryKey, Timestamped, Base):
    """Time-boxed claim on stock, created at checkout.

    Reservations expire so an abandoned checkout releases inventory instead of
    holding it forever. A sweeper job releases anything past ``expires_at``.
    """

    __tablename__ = "stock_reservations"
    __table_args__ = (Index("ix_reservations_expiry", "released_at", "expires_at"),)

    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(default=None, index=True)
    cart_id: Mapped[uuid.UUID | None] = mapped_column(default=None, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
