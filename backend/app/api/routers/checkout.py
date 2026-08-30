from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Header, status
from pydantic import BaseModel, Field

from app.api.deps import (
    CartDep,
    CheckoutDep,
    CurrentUser,
    IdempotencyDep,
    LocaleDep,
    PaymentsDep,
    UoWDep,
)
from app.core.errors import NotFoundError, ValidationFailedError
from app.modules.catalog.schemas import MoneyOut
from app.modules.orders.models import Order
from app.modules.orders.service import OrderQueryService, vat_breakdown
from app.shared.localization import resolve_translation

router = APIRouter(tags=["checkout"])


class CheckoutIn(BaseModel):
    shipping_address_id: uuid.UUID
    billing_address_id: uuid.UUID | None = None
    shipping_method: str = Field(default="standard", pattern="^(standard|express|pickup)$")
    accept_price_changes: bool = False


class OrderLineOut(BaseModel):
    sku: str
    title: str
    options: dict[str, str]
    image_url: str | None
    quantity: int
    unit_price: MoneyOut
    line_total: MoneyOut


class OrderOut(BaseModel):
    order_number: str
    status: str
    currency: str
    placed_at: str | None
    lines: list[OrderLineOut]
    subtotal: MoneyOut
    vat: MoneyOut
    shipping: MoneyOut
    total: MoneyOut
    vat_breakdown: dict[str, int]
    shipping_address: dict[str, Any]
    payment_redirect_url: str | None = None


def _serialise_order(order: Order, locale: str, redirect: str | None = None) -> OrderOut:
    return OrderOut(
        order_number=order.order_number,
        status=order.status.value,
        currency=order.currency,
        placed_at=order.placed_at.isoformat() if order.placed_at else None,
        lines=[
            OrderLineOut(
                sku=i.sku,
                title=resolve_translation(i.title_snapshot, locale),
                options=i.options_snapshot,
                image_url=i.image_url,
                quantity=i.quantity,
                unit_price=MoneyOut.of(i.unit_price_minor_units, order.currency, locale),
                line_total=MoneyOut.of(i.line_total_minor_units, order.currency, locale),
            )
            for i in order.items
        ],
        subtotal=MoneyOut.of(order.subtotal_minor_units, order.currency, locale),
        vat=MoneyOut.of(order.vat_minor_units, order.currency, locale),
        shipping=MoneyOut.of(order.shipping_minor_units, order.currency, locale),
        total=MoneyOut.of(order.total_minor_units, order.currency, locale),
        vat_breakdown=vat_breakdown(order),
        shipping_address=order.shipping_address,
        payment_redirect_url=redirect,
    )


@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def checkout(
    payload: CheckoutIn,
    user: CurrentUser,
    uow: UoWDep,
    carts: CartDep,
    service: CheckoutDep,
    payments: PaymentsDep,
    idempotency: IdempotencyDep,
    locale: LocaleDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    nm_cart: Annotated[str | None, Cookie(alias="nm_cart")] = None,
) -> OrderOut:
    """Place an order and open a payment intent.

    The Idempotency-Key header is mandatory: this endpoint moves money, and a
    retried request must return the original order rather than create a second
    one.
    """
    if not idempotency_key:
        raise ValidationFailedError("Idempotency-Key header is required for checkout")

    if cached := await idempotency.claim("checkout", idempotency_key):
        return OrderOut.model_validate(cached)

    try:
        cart = await carts.resolve(user_id=user.id, anonymous_token=nm_cart, create=False)
        if cart is None:
            raise NotFoundError("no open cart")

        order = await service.place_order(
            cart=cart,
            user_id=user.id,
            shipping_address_id=payload.shipping_address_id,
            billing_address_id=payload.billing_address_id,
            shipping_method=payload.shipping_method,
            accept_price_changes=payload.accept_price_changes,
            locale=locale,
        )
        payment = await payments.start(order)
        await uow.commit()
    except Exception:
        # Free the key so the shopper can correct the problem and retry.
        await idempotency.release("checkout", idempotency_key)
        raise

    result = _serialise_order(order, locale, payment.raw_response.get("redirect_url"))
    await idempotency.complete("checkout", idempotency_key, result.model_dump(mode="json"))
    return result


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    user: CurrentUser,
    uow: UoWDep,
    locale: LocaleDep,
    cursor: str | None = None,
    limit: int = 20,
) -> list[OrderOut]:
    page = await OrderQueryService(uow.session).list_for_customer(
        user.id, limit=limit, cursor=cursor
    )
    return [_serialise_order(o, locale) for o in page.items]


@router.get("/orders/{order_number}", response_model=OrderOut)
async def get_order(
    order_number: str, user: CurrentUser, uow: UoWDep, locale: LocaleDep
) -> OrderOut:
    order = await OrderQueryService(uow.session).get_for_customer(order_number, user.id)
    return _serialise_order(order, locale)


@router.post("/orders/{order_number}/cancel", response_model=OrderOut)
async def cancel_order(
    order_number: str,
    user: CurrentUser,
    uow: UoWDep,
    service: CheckoutDep,
    locale: LocaleDep,
) -> OrderOut:
    order = await OrderQueryService(uow.session).get_for_customer(order_number, user.id)
    await service.cancel(order, reason="cancelled_by_customer")
    await uow.commit()
    return _serialise_order(order, locale)
