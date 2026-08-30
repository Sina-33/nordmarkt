from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

TokenType = Literal["access", "refresh"]


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, stored: str) -> bool:
    try:
        _hasher.verify(stored, raw)
    except VerifyMismatchError:
        return False
    return True


def needs_rehash(stored: str) -> bool:
    return _hasher.check_needs_rehash(stored)


def issue_token(
    subject: uuid.UUID,
    token_type: TokenType,
    *,
    roles: tuple[str, ...] = (),
    session_id: uuid.UUID | None = None,
) -> str:
    settings = get_settings()
    ttl = (
        settings.access_token_ttl_seconds
        if token_type == "access"
        else settings.refresh_token_ttl_seconds
    )
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": secrets.token_urlsafe(16),
        "sid": str(session_id) if session_id else None,
    }
    if token_type == "access":
        payload["roles"] = list(roles)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("token expired") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("invalid token") from exc
    if claims.get("typ") != expected_type:
        raise UnauthorizedError("wrong token type")
    return claims
