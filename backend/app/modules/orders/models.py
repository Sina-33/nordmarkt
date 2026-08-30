from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.errors import ConflictError
from app.db.base import Base, Timestamped, UUIDPrimaryKey


class OrderStatus(enum.StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PACKING = "packing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# The state machine lives next to the aggregate, not scattered across services.
# Any transition not listed here is rejected, which is what stops a cancelled
# order from quietly becoming shipped.
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_PAYMENT: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.PACKING, OrderStatus.CANCELLED, OrderStatus.REFUNDED}),
    OrderStatus.PACKING: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED, OrderStatus.REFUNDED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}


class Order(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        CheckConstraint("total_minor_units >= 0", name="total_non_negative"),
    )

    order_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.PENDING_PAYMENT, index=True
    )

    currency: Mapped[str] = mapped_column(String(3), default="SEK")
    locale: Mapped[str] = mapped_column(String(5), default="sv")

    subtotal_minor_units: Mapped[int] = mapped_column(Integer)
    vat_minor_units: Mapped[int] = mapped_column(Integer)
    shipping_minor_units: Mapped[int] = mapped_column(Integer, default=0)
    discount_minor_units: Mapped[int] = mapped_column(Integer, default=0)
    total_minor_units: Mapped[int] = mapped_column(Integer)

    shipping_address: Mapped[dict[str, Any]]
    billing_address: Mapped[dict[str, Any]]
    shipping_method: Mapped[str] = mapped_column(String(32), default="standard")

    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, default=None)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    def transition_to(self, target: OrderStatus) -> None:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise ConflictError(
                f"cannot move order from {self.status.value} to {target.value}",
                current=self.status.value,
                requested=target.value,
            )
        self.status = target


class OrderItem(UUIDPrimaryKey, Base):
    """Line item with a full product snapshot.

    Orders are financial records. If a product is renamed, repriced or deleted
    the invoice must still read exactly as it did at purchase time, so nothing
    here is a live foreign-key lookup for display purposes.
    """

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id"))

    sku: Mapped[str] = mapped_column(String(64))
    title_snapshot: Mapped[dict[str, Any]]
    options_snapshot: Mapped[dict[str, Any]] = mapped_column(default=dict)
    image_url: Mapped[str | None] = mapped_column(Text, default=None)

    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor_units: Mapped[int] = mapped_column(Integer)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    line_total_minor_units: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
