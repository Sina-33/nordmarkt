from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CartDep, LocaleDep, OptionalUser, UoWDep
from app.core.errors import NotFoundError
from app.modules.catalog.repository import ProductRepository
from app.modules.catalog.schemas import MoneyOut
from app.shared.localization import resolve_translation

router = APIRouter(prefix="/cart", tags=["cart"])

ANON_COOKIE = "nm_cart"


class AddItemIn(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=99)


class SetQuantityIn(BaseModel):
    quantity: int = Field(ge=0, le=99)


class CartLineOut(BaseModel):
    variant_id: uuid.UUID
    sku: str
    title: str
    options: dict[str, str]
    image_url: str | None
    quantity: int
    unit_price: MoneyOut
    line_total: MoneyOut
    price_changed: bool


class CartOut(BaseModel):
    id: uuid.UUID
    currency: str
    item_count: int
    lines: list[CartLineOut]
    subtotal: MoneyOut
    vat_included: MoneyOut
    shipping: MoneyOut
    total: MoneyOut
    free_shipping_remaining: MoneyOut | None


async def _serialise(cart, service, uow, locale: str) -> CartOut:
    products = ProductRepository(uow.session)
    variants = await products.get_variants([i.variant_id for i in cart.items])
    totals = await service.totals(cart)

    lines: list[CartLineOut] = []
    for item in cart.items:
        variant = variants.get(item.variant_id)
        if variant is None:
            continue
        product = variant.product
        lines.append(
            CartLineOut(
                variant_id=variant.id,
                sku=variant.sku,
                title=resolve_translation(product.title, locale),
                options=variant.options,
                image_url=product.images[0].url if product.images else None,
                quantity=item.quantity,
                unit_price=MoneyOut.of(variant.price_minor_units, variant.currency, locale),
                line_total=MoneyOut.of(
                    variant.price_minor_units * item.quantity, variant.currency, locale
                ),
                price_changed=variant.price_minor_units != item.unit_price_minor_units,
            )
        )

    from app.modules.cart.service import FREE_SHIPPING_THRESHOLD

    remaining = FREE_SHIPPING_THRESHOLD.minor_units - totals.subtotal.minor_units
    return CartOut(
        id=cart.id,
        currency=cart.currency,
        item_count=totals.item_count,
        lines=lines,
        subtotal=MoneyOut.of(totals.subtotal.minor_units, cart.currency, locale),
        vat_included=MoneyOut.of(totals.vat.minor_units, cart.currency, locale),
        shipping=MoneyOut.of(totals.shipping.minor_units, cart.currency, locale),
        total=MoneyOut.of(totals.total.minor_units, cart.currency, locale),
        free_shipping_remaining=(
            MoneyOut.of(remaining, cart.currency, locale) if remaining > 0 else None
        ),
    )


@router.get("", response_model=CartOut)
async def read_cart(
    uow: UoWDep,
    service: CartDep,
    locale: LocaleDep,
    user: OptionalUser,
    response: Response,
    nm_cart: Annotated[str | None, Cookie(alias=ANON_COOKIE)] = None,
) -> CartOut:
    cart = await service.resolve(
        user_id=user.id if user else None, anonymous_token=nm_cart, create=True
    )
    assert cart is not None
    if cart.anonymous_token and cart.anonymous_token != nm_cart:
        # HttpOnly so a stored-XSS payload cannot lift the basket token.
        response.set_cookie(
            ANON_COOKIE,
            cart.anonymous_token,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax",
        )
    await uow.commit()
    return await _serialise(cart, service, uow, locale)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    payload: AddItemIn,
    uow: UoWDep,
    service: CartDep,
    locale: LocaleDep,
    user: OptionalUser,
    response: Response,
    nm_cart: Annotated[str | None, Cookie(alias=ANON_COOKIE)] = None,
) -> CartOut:
    cart = await service.resolve(
        user_id=user.id if user else None, anonymous_token=nm_cart, create=True
    )
    assert cart is not None
    cart = await service.add_item(cart, payload.variant_id, payload.quantity)
    if cart.anonymous_token and cart.anonymous_token != nm_cart:
        response.set_cookie(
            ANON_COOKIE,
            cart.anonymous_token,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax",
        )
    await uow.commit()
    return await _serialise(cart, service, uow, locale)


@router.patch("/items/{variant_id}", response_model=CartOut)
async def set_quantity(
    variant_id: uuid.UUID,
    payload: SetQuantityIn,
    uow: UoWDep,
    service: CartDep,
    locale: LocaleDep,
    user: OptionalUser,
    nm_cart: Annotated[str | None, Cookie(alias=ANON_COOKIE)] = None,
) -> CartOut:
    cart = await service.resolve(
        user_id=user.id if user else None, anonymous_token=nm_cart, create=False
    )
    if cart is None:
        raise NotFoundError("no open cart")
    cart = await service.set_quantity(cart, variant_id, payload.quantity)
    await uow.commit()
    return await _serialise(cart, service, uow, locale)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    uow: UoWDep,
    service: CartDep,
    user: OptionalUser,
    nm_cart: Annotated[str | None, Cookie(alias=ANON_COOKIE)] = None,
) -> None:
    cart = await service.resolve(
        user_id=user.id if user else None, anonymous_token=nm_cart, create=False
    )
    if cart is not None:
        await service.clear(cart)
        await uow.commit()
