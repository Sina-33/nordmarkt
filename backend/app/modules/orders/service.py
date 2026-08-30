"""Checkout orchestration.

Checkout is where every other module meets, so it is the one place worth
spelling out the ordering rules:

1. Re-price from the live catalogue. The cart's stored price is advisory only;
   charging a stale price is a legal problem in the EU, not just a bug.
2. Reserve stock *before* creating the order. A reservation that fails must
   not leave a half-written order behind.
3. Snapshot everything onto the order rows. Orders are immutable records.
4. Emit ``order.placed`` through the outbox in the same transaction.

Steps 1-4 run inside one Unit of Work. Either the shopper has an order and the
stock is held, or nothing happened at all.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CartEmptyError, ForbiddenError, NotFoundError, PriceChangedError
from app.core.logging import get_logger
from app.core.money import Money
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.cart.models import Cart
from app.modules.cart.service import CartService
from app.modules.catalog.repository import ProductRepository
from app.modules.identity.models import Address
from app.modules.inventory.models import StockReservation
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.shared.events import OrderCancelled, OrderPaid, OrderPlaced
from app.shared.unit_of_work import UnitOfWork

logger = get_logger(__name__)


def generate_order_number(now: datetime | None = None) -> str:
    """Human-quotable order number: NM-250830-K4F7QX.

    Sequential integers leak volume to competitors and make enumeration
    trivial; a raw UUID is unreadable over the phone to support. This is dated
    for operations plus 6 random base32 characters for unguessability.
    """
    stamp = (now or datetime.now(UTC)).strftime("%y%m%d")
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"NM-{stamp}-{suffix}"


class CheckoutService:
    def __init__(
        self,
        uow: UnitOfWork,
        cart_service: CartService,
        inventory: InventoryService,
    ) -> None:
        self._uow = uow
        self._carts = cart_service
        self._inventory = inventory
        self._products = ProductRepository(uow.session)

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def place_order(
        self,
        *,
        cart: Cart,
        user_id: uuid.UUID,
        shipping_address_id: uuid.UUID,
        billing_address_id: uuid.UUID | None = None,
        shipping_method: str = "standard",
        accept_price_changes: bool = False,
        locale: str = "sv",
    ) -> Order:
        if not cart.items:
            raise CartEmptyError("cannot check out an empty cart")

        drift = await self._carts.repricing_report(cart)
        if drift and not accept_price_changes:
            raise PriceChangedError("prices changed since these items were added", changes=drift)

        shipping = await self._load_address(shipping_address_id, user_id)
        billing = (
            await self._load_address(billing_address_id, user_id)
            if billing_address_id and billing_address_id != shipping_address_id
            else shipping
        )

        variants = await self._products.get_variants([i.variant_id for i in cart.items])
        totals = await self._carts.totals(cart)

        order = Order(
            order_number=generate_order_number(),
            customer_id=user_id,
            currency=cart.currency,
            locale=locale,
            subtotal_minor_units=totals.subtotal.minor_units,
            vat_minor_units=totals.vat.minor_units,
            shipping_minor_units=totals.shipping.minor_units,
            total_minor_units=totals.total.minor_units,
            shipping_address=shipping.snapshot(),
            billing_address=billing.snapshot(),
            shipping_method=shipping_method,
            placed_at=datetime.now(UTC),
        )
        self._session.add(order)
        await self._session.flush()

        # Reserve first, then attach lines. Any InsufficientStockError raised here
        # propagates out of the Unit of Work and rolls the order back with it.
        for line in cart.items:
            variant = variants.get(line.variant_id)
            if variant is None or not variant.is_active:
                raise NotFoundError("a product in the cart is no longer available")

            await self._inventory.reserve(variant.id, line.quantity, order_id=order.id)

            unit = Money(variant.price_minor_units, variant.currency)
            product = variant.product
            self._session.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=variant.id,
                    sku=variant.sku,
                    title_snapshot=product.title,
                    options_snapshot=variant.options,
                    image_url=product.images[0].url if product.images else None,
                    quantity=line.quantity,
                    unit_price_minor_units=variant.price_minor_units,
                    vat_rate=variant.vat_rate,
                    line_total_minor_units=(unit * line.quantity).minor_units,
                )
            )

        cart.checked_out_at = datetime.now(UTC)

        self._uow.emit(
            OrderPlaced(
                aggregate_id=order.id,
                order_number=order.order_number,
                customer_id=user_id,
                total_minor_units=order.total_minor_units,
                currency=order.currency,
                locale=locale,
            )
        )
        await self._session.flush()
        logger.info(
            "order_placed",
            order_number=order.order_number,
            lines=len(cart.items),
            total=order.total_minor_units,
        )
        return order

    async def mark_paid(self, order: Order, payment_reference: str) -> Order:
        order.transition_to(OrderStatus.PAID)
        order.paid_at = datetime.now(UTC)

        for reservation in await self._reservations_for(order.id):
            await self._inventory.commit_reservation(reservation)

        self._uow.emit(
            OrderPaid(
                aggregate_id=order.id,
                order_number=order.order_number,
                payment_reference=payment_reference,
            )
        )
        return order

    async def cancel(self, order: Order, reason: str) -> Order:
        order.transition_to(OrderStatus.CANCELLED)
        order.cancelled_at = datetime.now(UTC)
        order.cancellation_reason = reason

        for reservation in await self._reservations_for(order.id):
            await self._inventory.release(reservation)

        self._uow.emit(
            OrderCancelled(aggregate_id=order.id, order_number=order.order_number, reason=reason)
        )
        return order

    async def _reservations_for(self, order_id: uuid.UUID) -> list[StockReservation]:
        stmt = select(StockReservation).where(
            StockReservation.order_id == order_id,
            StockReservation.released_at.is_(None),
            StockReservation.committed_at.is_(None),
        )
        return list((await self._session.scalars(stmt)).all())

    async def _load_address(self, address_id: uuid.UUID, user_id: uuid.UUID) -> Address:
        address = await self._session.get(Address, address_id)
        if address is None:
            raise NotFoundError("address not found")
        if address.user_id != user_id:
            # Deliberately a 403 and not a 404: the caller is authenticated and
            # the resource exists, it just is not theirs.
            raise ForbiddenError("address belongs to another account")
        return address


class OrderQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_customer(self, order_number: str, user_id: uuid.UUID) -> Order:
        order = await self._session.scalar(select(Order).where(Order.order_number == order_number))
        if order is None:
            raise NotFoundError("order not found")
        if order.customer_id != user_id:
            raise ForbiddenError("order belongs to another account")
        return order

    async def list_for_customer(
        self, user_id: uuid.UUID, *, limit: int = 20, cursor: str | None = None
    ) -> Page[Order]:
        stmt = select(Order).where(Order.customer_id == user_id)
        if cursor:
            stmt = stmt.where(Order.created_at < decode_cursor(cursor)["created_at"])
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit + 1)

        rows = list((await self._session.scalars(stmt)).all())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_cursor({"created_at": items[-1].created_at.isoformat()})
            if has_more and items
            else None
        )
        return Page(items=items, next_cursor=next_cursor)


def vat_breakdown(order: Order) -> dict[str, int]:
    """Per-rate VAT split, required on Swedish invoices."""
    buckets: dict[str, int] = {}
    for item in order.items:
        rate: Decimal = item.vat_rate
        gross = Money(item.line_total_minor_units, order.currency)
        amount = gross.apply_rate(rate / (Decimal(1) + rate))
        key = f"{rate:.3f}"
        buckets[key] = buckets.get(key, 0) + amount.minor_units
    return buckets
