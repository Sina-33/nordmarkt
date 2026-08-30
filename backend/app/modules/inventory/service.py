"""Inventory service.

Overselling is the defining correctness problem of a storefront. Two shoppers
hit the last unit at the same millisecond; without a locking strategy both
succeed and one of them gets an apology email.

The approach here is a conditional UPDATE rather than read-then-write:

    UPDATE stock_items SET reserved = reserved + :qty
    WHERE variant_id = :v AND on_hand - reserved >= :qty

Postgres evaluates the predicate under the row lock it already takes for the
write, so the check and the increment are one atomic step. ``rowcount == 0``
means somebody else won the race - no application-level retry loop, no
distributed lock, no Redis mutex that fails open during a failover.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InsufficientStockError
from app.core.logging import get_logger
from app.modules.inventory.models import StockItem, StockReservation
from app.shared.events import StockRanLow, StockReserved
from app.shared.unit_of_work import UnitOfWork

logger = get_logger(__name__)

RESERVATION_TTL = timedelta(minutes=20)


class InventoryService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def sellable_map(self, variant_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not variant_ids:
            return {}
        stmt = select(StockItem).where(StockItem.variant_id.in_(variant_ids))
        result: dict[uuid.UUID, int] = {}
        for item in (await self._session.scalars(stmt)).all():
            result[item.variant_id] = result.get(item.variant_id, 0) + item.sellable
        return result

    async def reserve(
        self,
        variant_id: uuid.UUID,
        quantity: int,
        *,
        cart_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
    ) -> StockReservation:
        stmt = (
            update(StockItem)
            .where(
                StockItem.variant_id == variant_id,
                StockItem.on_hand - StockItem.reserved >= quantity,
            )
            .values(reserved=StockItem.reserved + quantity)
            .returning(
                StockItem.id, StockItem.on_hand, StockItem.reserved, StockItem.low_stock_threshold
            )
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            available = (await self.sellable_map([variant_id])).get(variant_id, 0)
            raise InsufficientStockError(
                "not enough stock to reserve",
                variant_id=str(variant_id),
                requested=quantity,
                available=available,
            )

        reservation = StockReservation(
            variant_id=variant_id,
            quantity=quantity,
            cart_id=cart_id,
            order_id=order_id,
            expires_at=datetime.now(UTC) + RESERVATION_TTL,
        )
        self._session.add(reservation)
        await self._session.flush()

        self._uow.emit(
            StockReserved(
                aggregate_id=variant_id,
                variant_id=variant_id,
                quantity=quantity,
                reservation_id=reservation.id,
            )
        )

        remaining = row.on_hand - row.reserved
        if remaining <= row.low_stock_threshold:
            self._uow.emit(
                StockRanLow(
                    aggregate_id=variant_id,
                    variant_id=variant_id,
                    remaining=remaining,
                    threshold=row.low_stock_threshold,
                )
            )
        return reservation

    async def commit_reservation(self, reservation: StockReservation) -> None:
        """Convert a reservation into a permanent stock decrement (on payment)."""
        await self._session.execute(
            update(StockItem)
            .where(StockItem.variant_id == reservation.variant_id)
            .values(
                on_hand=StockItem.on_hand - reservation.quantity,
                reserved=StockItem.reserved - reservation.quantity,
            )
        )
        reservation.committed_at = datetime.now(UTC)

    async def release(self, reservation: StockReservation) -> None:
        if reservation.released_at or reservation.committed_at:
            return  # already settled; releasing twice would corrupt the counter
        await self._session.execute(
            update(StockItem)
            .where(StockItem.variant_id == reservation.variant_id)
            .values(reserved=StockItem.reserved - reservation.quantity)
        )
        reservation.released_at = datetime.now(UTC)

    async def release_expired(self, limit: int = 200) -> int:
        """Sweeper for abandoned checkouts. Idempotent by construction."""
        stmt = (
            select(StockReservation)
            .where(
                StockReservation.released_at.is_(None),
                StockReservation.committed_at.is_(None),
                StockReservation.expires_at < datetime.now(UTC),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        expired = list((await self._session.scalars(stmt)).all())
        for reservation in expired:
            await self.release(reservation)
        if expired:
            logger.info("released_expired_reservations", count=len(expired))
        return len(expired)

    async def restock(
        self, variant_id: uuid.UUID, quantity: int, warehouse: str = "SE-STO"
    ) -> None:
        item = await self._session.scalar(
            select(StockItem).where(
                StockItem.variant_id == variant_id, StockItem.warehouse_code == warehouse
            )
        )
        if item is None:
            item = StockItem(variant_id=variant_id, warehouse_code=warehouse, on_hand=0)
            self._session.add(item)
        item.on_hand += quantity
