from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import BigInteger, DateTime, MetaData, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Explicit naming convention so Alembic autogenerates stable constraint names
# instead of database-assigned ones that differ between environments.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB,
        uuid.UUID: PGUUID(as_uuid=True),
    }


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(UTC)
    )


class OptimisticLock:
    """Row version for lost-update prevention on concurrently edited aggregates."""

    version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)

    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": None}


class SoftDelete:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Sluggable:
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
