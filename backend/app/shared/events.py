from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    aggregate_type: str
    aggregate_id: uuid.UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        raise NotImplementedError

    def to_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("aggregate_type", None)
        return data


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPlaced(DomainEvent):
    aggregate_type: str = "order"
    order_number: str
    customer_id: uuid.UUID
    total_minor_units: int
    currency: str
    locale: str

    @property
    def event_type(self) -> str:
        return "order.placed"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPaid(DomainEvent):
    aggregate_type: str = "order"
    order_number: str
    payment_reference: str

    @property
    def event_type(self) -> str:
        return "order.paid"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCancelled(DomainEvent):
    aggregate_type: str = "order"
    order_number: str
    reason: str

    @property
    def event_type(self) -> str:
        return "order.cancelled"


@dataclass(frozen=True, slots=True, kw_only=True)
class StockReserved(DomainEvent):
    aggregate_type: str = "inventory"
    variant_id: uuid.UUID
    quantity: int
    reservation_id: uuid.UUID

    @property
    def event_type(self) -> str:
        return "inventory.reserved"


@dataclass(frozen=True, slots=True, kw_only=True)
class StockRanLow(DomainEvent):
    aggregate_type: str = "inventory"
    variant_id: uuid.UUID
    remaining: int
    threshold: int

    @property
    def event_type(self) -> str:
        return "inventory.ran_low"
