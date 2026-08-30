from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import CartDep, CurrentUser, IdentityDep, UoWDep
from app.core.security import decode_token

router = APIRouter(prefix="/auth", tags=["identity"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    locale: str = Field(default="sv", pattern="^(sv|en)$")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    preferred_locale: str
    roles: list[str]


class AddressIn(BaseModel):
    recipient: str = Field(max_length=160)
    street: str = Field(max_length=240)
    postal_code: str = Field(max_length=16)
    city: str = Field(max_length=120)
    country_code: str = Field(default="SE", min_length=2, max_length=2)
    phone: str | None = Field(default=None, max_length=32)
    is_default: bool = False


class AddressOut(AddressIn):
    id: uuid.UUID


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn, uow: UoWDep, identity: IdentityDep, request: Request
) -> TokenOut:
    user = await identity.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        locale=payload.locale,
    )
    tokens = await identity.start_session(
        user, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None
    )
    await uow.commit()
    return TokenOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    uow: UoWDep,
    identity: IdentityDep,
    carts: CartDep,
    request: Request,
    nm_cart: Annotated[str | None, Cookie(alias="nm_cart")] = None,
) -> TokenOut:
    user = await identity.authenticate(payload.email, payload.password)
    if nm_cart:
        await carts.merge_guest_cart(user.id, nm_cart)
    tokens = await identity.start_session(
        user,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    await uow.commit()
    return TokenOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn, uow: UoWDep, identity: IdentityDep) -> TokenOut:
    tokens = await identity.rotate(payload.refresh_token)
    await uow.commit()
    return TokenOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshIn, uow: UoWDep, identity: IdentityDep) -> None:
    claims = decode_token(payload.refresh_token, "refresh")
    await identity.sign_out(uuid.UUID(claims["sid"]))
    await uow.commit()


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        preferred_locale=user.preferred_locale,
        roles=list(user.roles),
    )


@router.get("/me/addresses", response_model=list[AddressOut])
async def list_addresses(user: CurrentUser) -> list[AddressOut]:
    return [
        AddressOut(
            id=a.id,
            recipient=a.recipient,
            street=a.street,
            postal_code=a.postal_code,
            city=a.city,
            country_code=a.country_code,
            phone=a.phone,
            is_default=a.is_default,
        )
        for a in user.addresses
    ]


@router.post("/me/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def add_address(
    payload: AddressIn, user: CurrentUser, uow: UoWDep, identity: IdentityDep
) -> AddressOut:
    address = await identity.add_address(user.id, **payload.model_dump())
    await uow.commit()
    return AddressOut(id=address.id, **payload.model_dump())
