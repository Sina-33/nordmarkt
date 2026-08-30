from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InsufficientStock, NotFound, ValidationFailed
from app.core.money import Money
from app.modules.cart.models import Cart, CartItem
from app.modules.catalog.repository import ProductRepository
from app.modules.inventory.service import InventoryService
from app.shared.unit_of_work import UnitOfWork

MAX_LINE_QUANTITY = 99
MAX_DISTINCT_LINES = 50


class CartTotals:
    __slots__ = ("subtotal", "vat", "shipping", "total", "item_count")

    def __init__(self, subtotal: Money, vat: Money, shipping: Money, item_count: int) -> None:
        self.subtotal = subtotal
        self.vat = vat
        self.shipping = shipping
        self.total = subtotal + shipping
        self.item_count = item_count


# Free shipping over 995 kr - the threshold lives here rather than in the
# frontend so the number the shopper sees and the number they are charged can
# never disagree.
FREE_SHIPPING_THRESHOLD = Money(99_500, "SEK")
STANDARD_SHIPPING = Money(4_900, "SEK")


class CartService:
    def __init__(self, uow: UnitOfWork, inventory: InventoryService) -> None:
        self._uow = uow
        self._inventory = inventory
        self._products = ProductRepository(uow.session)

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def resolve(
        self,
        *,
        user_id: uuid.UUID | None,
        anonymous_token: str | None,
        create: bool = True,
    ) -> Cart | None:
        stmt = select(Cart).where(Cart.checked_out_at.is_(None))
        if user_id:
            cart = await self._session.scalar(stmt.where(Cart.user_id == user_id))
        elif anonymous_token:
            cart = await self._session.scalar(
                stmt.where(Cart.anonymous_token == anonymous_token)
            )
        else:
            cart = None

        if cart or not create:
            return cart

        cart = Cart(
            user_id=user_id,
            anonymous_token=None if user_id else (anonymous_token or secrets.token_urlsafe(24)),
        )
        self._session.add(cart)
        await self._session.flush()
        return cart

    async def merge_guest_cart(self, user_id: uuid.UUID, anonymous_token: str) -> Cart:
        """Fold a guest basket into the user's basket at sign-in.

        Quantities are summed and clamped rather than overwritten: the shopper
        added both sets of items deliberately, so silently dropping either half
        is the wrong default.
        """
        guest = await self.resolve(user_id=None, anonymous_token=anonymous_token, create=False)
        target = await self.resolve(user_id=user_id, anonymous_token=None, create=True)
        assert target is not None

        if guest is None or guest.id == target.id:
            return target

        existing = {item.variant_id: item for item in target.items}
        for item in guest.items:
            if match := existing.get(item.variant_id):
                match.quantity = min(match.quantity + item.quantity, MAX_LINE_QUANTITY)
            else:
                self._session.add(
                    CartItem(
                        cart_id=target.id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                        unit_price_minor_units=item.unit_price_minor_units,
                    )
                )
        await self._session.delete(guest)
        await self._session.flush()
        await self._session.refresh(target)
        return target

    async def add_item(self, cart: Cart, variant_id: uuid.UUID, quantity: int) -> Cart:
        if quantity < 1:
            raise ValidationFailed("quantity must be at least 1")

        variant = await self._products.get_variant(variant_id)
        if variant is None or not variant.is_active:
            raise NotFound("variant not available", variant_id=str(variant_id))

        line = next((i for i in cart.items if i.variant_id == variant_id), None)
        target_quantity = min((line.quantity if line else 0) + quantity, MAX_LINE_QUANTITY)

        sellable = (await self._inventory.sellable_map([variant_id])).get(variant_id, 0)
        if sellable < target_quantity:
            raise InsufficientStock(
                "requested quantity exceeds available stock",
                available=sellable,
                requested=target_quantity,
            )

        if line is None:
            if len(cart.items) >= MAX_DISTINCT_LINES:
                raise ValidationFailed("cart line limit reached", limit=MAX_DISTINCT_LINES)
            self._session.add(
                CartItem(
                    cart_id=cart.id,
                    variant_id=variant_id,
                    quantity=target_quantity,
                    unit_price_minor_units=variant.price_minor_units,
                )
            )
        else:
            line.quantity = target_quantity
            line.unit_price_minor_units = variant.price_minor_units

        await self._session.flush()
        await self._session.refresh(cart)
        return cart

    async def set_quantity(self, cart: Cart, variant_id: uuid.UUID, quantity: int) -> Cart:
        line = next((i for i in cart.items if i.variant_id == variant_id), None)
        if line is None:
            raise NotFound("line not in cart")
        if quantity <= 0:
            await self._session.delete(line)
        else:
            sellable = (await self._inventory.sellable_map([variant_id])).get(variant_id, 0)
            if sellable < quantity:
                raise InsufficientStock("not enough stock", available=sellable, requested=quantity)
            line.quantity = min(quantity, MAX_LINE_QUANTITY)
        await self._session.flush()
        await self._session.refresh(cart)
        return cart

    async def clear(self, cart: Cart) -> None:
        for line in list(cart.items):
            await self._session.delete(line)
        await self._session.flush()

    async def repricing_report(self, cart: Cart) -> list[dict[str, object]]:
        """Detect drift between the price shown when added and the live price."""
        variants = await self._products.get_variants([i.variant_id for i in cart.items])
        drifted: list[dict[str, object]] = []
        for line in cart.items:
            variant = variants.get(line.variant_id)
            if variant and variant.price_minor_units != line.unit_price_minor_units:
                drifted.append(
                    {
                        "variant_id": str(line.variant_id),
                        "was": line.unit_price_minor_units,
                        "now": variant.price_minor_units,
                    }
                )
        return drifted

    async def totals(self, cart: Cart) -> CartTotals:
        variants = await self._products.get_variants([i.variant_id for i in cart.items])
        subtotal = Money(0, cart.currency)
        vat = Money(0, cart.currency)
        count = 0

        for line in cart.items:
            variant = variants.get(line.variant_id)
            if variant is None:
                continue
            unit = Money(variant.price_minor_units, variant.currency)
            line_total = unit * line.quantity
            subtotal = subtotal + line_total
            # Swedish prices are quoted VAT-inclusive, so VAT is extracted from
            # the gross amount rather than added on top.
            rate: Decimal = variant.vat_rate
            vat = vat + line_total.apply_rate(rate / (Decimal(1) + rate))
            count += line.quantity

        shipping = (
            Money(0, cart.currency)
            if subtotal.minor_units >= FREE_SHIPPING_THRESHOLD.minor_units or subtotal.is_zero
            else STANDARD_SHIPPING
        )
        return CartTotals(subtotal=subtotal, vat=vat, shipping=shipping, item_count=count)
