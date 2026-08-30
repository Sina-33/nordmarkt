from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import (
    decode_token,
    hash_password,
    issue_token,
    needs_rehash,
    verify_password,
)
from app.modules.identity.models import Address, SessionToken, User
from app.shared.unit_of_work import UnitOfWork


class TokenPair:
    __slots__ = ("access_token", "expires_in", "refresh_token")

    def __init__(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in


def _fingerprint(token: str) -> str:
    """Refresh tokens are stored hashed.

    A database dump should not hand an attacker a set of working credentials.
    SHA-256 is sufficient here because the token is already 128+ bits of
    entropy - it needs no key stretching, unlike a human-chosen password.
    """
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def register(
        self, *, email: str, password: str, full_name: str, locale: str = "sv"
    ) -> User:
        normalised = email.strip().lower()
        exists = await self._session.scalar(select(User.id).where(User.email == normalised))
        if exists:
            raise ConflictError("an account with this email already exists")

        user = User(
            email=normalised,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            preferred_locale=locale,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self._session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            # Run a hash anyway so response time does not reveal whether the
            # address exists. Cheap defence against user enumeration.
            hash_password(password)
            raise UnauthorizedError("invalid credentials")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("invalid credentials")
        if not user.is_active:
            raise UnauthorizedError("account is disabled")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        return user

    async def start_session(
        self, user: User, *, user_agent: str | None = None, ip: str | None = None
    ) -> TokenPair:
        settings = get_settings()
        session_id = uuid.uuid4()
        refresh = issue_token(user.id, "refresh", session_id=session_id)

        self._session.add(
            SessionToken(
                id=session_id,
                user_id=user.id,
                token_hash=_fingerprint(refresh),
                user_agent=(user_agent or "")[:320] or None,
                ip_address=ip,
                expires_at=datetime.now(UTC)
                + timedelta(seconds=settings.refresh_token_ttl_seconds),
            )
        )
        access = issue_token(user.id, "access", roles=tuple(user.roles), session_id=session_id)
        return TokenPair(access, refresh, settings.access_token_ttl_seconds)

    async def rotate(self, refresh_token: str) -> TokenPair:
        """Refresh-token rotation with reuse detection.

        Each refresh issues a brand new token and retires the old one. If a
        retired token is presented again the family is assumed stolen and every
        session for that user is revoked.
        """
        claims = decode_token(refresh_token, "refresh")
        session_id = uuid.UUID(claims["sid"])
        record = await self._session.get(SessionToken, session_id)

        if record is None or record.token_hash != _fingerprint(refresh_token):
            if record is not None:
                await self._revoke_all(record.user_id)
            raise UnauthorizedError("refresh token rejected")
        if record.revoked_at or record.expires_at < datetime.now(UTC):
            raise UnauthorizedError("session expired")

        user = await self._session.get(User, record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("account unavailable")

        record.revoked_at = datetime.now(UTC)
        return await self.start_session(user, user_agent=record.user_agent, ip=record.ip_address)

    async def sign_out(self, session_id: uuid.UUID) -> None:
        await self._session.execute(
            update(SessionToken)
            .where(SessionToken.id == session_id, SessionToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def _revoke_all(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(SessionToken)
            .where(SessionToken.user_id == user_id, SessionToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def add_address(self, user_id: uuid.UUID, **fields: object) -> Address:
        address = Address(user_id=user_id, **fields)  # type: ignore[arg-type]
        if address.is_default:
            await self._session.execute(
                update(Address).where(Address.user_id == user_id).values(is_default=False)
            )
        self._session.add(address)
        await self._session.flush()
        return address

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError("user not found")
        return user


def new_anonymous_token() -> str:
    return secrets.token_urlsafe(24)
