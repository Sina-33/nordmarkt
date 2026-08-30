from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Header, Request
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.idempotency import IdempotencyStore
from app.core.logging import actor_id_ctx
from app.core.security import decode_token
from app.db.session import get_session_factory
from app.modules.cart.service import CartService
from app.modules.identity.models import User
from app.modules.identity.service import IdentityService
from app.modules.inventory.service import InventoryService
from app.modules.orders.service import CheckoutService
from app.modules.payments.service import PaymentService, SandboxGateway
from app.shared.localization import negotiate_locale
from app.shared.unit_of_work import UnitOfWork

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_uow() -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(get_session_factory()) as uow:
        yield uow


UoWDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


async def get_locale(
    settings: SettingsDep,
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
    x_locale: Annotated[str | None, Header(alias="X-Locale")] = None,
) -> str:
    """Explicit header wins over browser negotiation.

    The frontend sets X-Locale from the URL segment (/sv, /en) because the URL
    is the source of truth for language - a Swedish browser must still get
    English content when the shopper picked /en.
    """
    if x_locale in settings.supported_locales:
        return x_locale
    return negotiate_locale(accept_language, settings.supported_locales, settings.default_locale)


LocaleDep = Annotated[str, Depends(get_locale)]


async def get_current_user(
    uow: UoWDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("missing bearer token")
    claims = decode_token(authorization.split(" ", 1)[1], "access")
    user = await uow.session.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("account unavailable")
    actor_id_ctx.set(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    uow: UoWDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Anonymous browsing must work everywhere, so auth is optional by default."""
    if not authorization:
        return None
    try:
        return await get_current_user(uow, authorization)
    except UnauthorizedError:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    async def guard(user: CurrentUser) -> User:
        if not any(user.has_role(role) for role in roles):
            raise ForbiddenError("insufficient role", required=list(roles))
        return user

    return guard


AdminUser = Annotated[User, Depends(require_roles("admin", "staff"))]


def get_inventory(uow: UoWDep) -> InventoryService:
    return InventoryService(uow)


InventoryDep = Annotated[InventoryService, Depends(get_inventory)]


def get_cart_service(uow: UoWDep, inventory: InventoryDep) -> CartService:
    return CartService(uow, inventory)


CartDep = Annotated[CartService, Depends(get_cart_service)]


def get_checkout(uow: UoWDep, carts: CartDep, inventory: InventoryDep) -> CheckoutService:
    return CheckoutService(uow, carts, inventory)


CheckoutDep = Annotated[CheckoutService, Depends(get_checkout)]


def get_identity(uow: UoWDep) -> IdentityService:
    return IdentityService(uow)


IdentityDep = Annotated[IdentityService, Depends(get_identity)]


def get_payments(uow: UoWDep) -> PaymentService:
    return PaymentService(uow, SandboxGateway())


PaymentsDep = Annotated[PaymentService, Depends(get_payments)]


def get_idempotency(redis: Annotated[Redis, Depends(get_redis)]) -> IdempotencyStore:
    return IdempotencyStore(redis)


IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency)]
