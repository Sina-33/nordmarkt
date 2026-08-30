from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class PaymentStatus(str, enum.Enum):
    INITIATED = "initiated"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("provider_reference", name="uq_payments_provider_ref"),)

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="swish_sandbox")
    provider_reference: Mapped[str] = mapped_column(String(96))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.INITIATED
    )
    amount_minor_units: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="SEK")
    failure_reason: Mapped[str | None] = mapped_column(Text, default=None)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    raw_response: Mapped[dict[str, Any]] = mapped_column(default=dict)


class ProcessedWebhook(UUIDPrimaryKey, Timestamped, Base):
    """Dedupe table for provider callbacks.

    Payment providers retry aggressively and guarantee at-least-once delivery.
    Inserting the provider's event id under a unique constraint turns a
    duplicate callback into a cheap no-op instead of a double capture.
    """

    __tablename__ = "processed_webhooks"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)

    provider: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
