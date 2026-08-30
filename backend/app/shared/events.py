from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any


def _jsonable(value: Any) -> Any:
    """Coerce a value into something ``json.dumps`` accepts.

    The payload lands in a JSONB column, so UUIDs and datetimes have to be
    rendered here rather than at the driver. Every event carries at least one
    UUID, so without this no event can be written to the outbox at all.
    """
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


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
        return {key: _jsonable(value) for key, value in data.items()}


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
