from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(160))
    preferred_locale: Mapped[str] = mapped_column(String(5), default="sv")
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=lambda: ["customer"])
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    addresses: Mapped[list[Address]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    sessions: Mapped[list[SessionToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def has_role(self, role: str) -> bool:
        return role in self.roles


class Address(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient: Mapped[str] = mapped_column(String(160))
    street: Mapped[str] = mapped_column(String(240))
    postal_code: Mapped[str] = mapped_column(String(16))
    city: Mapped[str] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), default="SE")
    phone: Mapped[str | None] = mapped_column(String(32), default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="addresses")

    def snapshot(self) -> dict[str, Any]:
        """Frozen copy stored on the order.

        An order must remember where it was actually shipped even if the
        customer edits or deletes the address afterwards.
        """
        return {
            "recipient": self.recipient,
            "street": self.street,
            "postal_code": self.postal_code,
            "city": self.city,
            "country_code": self.country_code,
            "phone": self.phone,
        }


class SessionToken(UUIDPrimaryKey, Timestamped, Base):
    """Server-side handle for a refresh token.

    The refresh JWT carries only a session id; revocation is a single UPDATE
    here, which is what makes "sign out of all devices" actually work.
    """

    __tablename__ = "session_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(320), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    user: Mapped[User] = relationship(back_populates="sessions")
