from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Sluggable, SoftDelete, Timestamped, UUIDPrimaryKey


class Category(UUIDPrimaryKey, Timestamped, Sluggable, Base):
    __tablename__ = "categories"

    name: Mapped[dict[str, Any]]
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), default=None
    )
    # Materialised path ("home.furniture.seating") so a whole subtree is one
    # indexed prefix scan instead of a recursive CTE on every request.
    path: Mapped[str] = mapped_column(String(512), index=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)

    children: Mapped[list[Category]] = relationship(back_populates="parent")
    parent: Mapped[Category | None] = relationship(
        back_populates="children", remote_side="Category.id"
    )


class Brand(UUIDPrimaryKey, Timestamped, Sluggable, Base):
    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(160))
    country_code: Mapped[str | None] = mapped_column(String(2), default=None)
    logo_url: Mapped[str | None] = mapped_column(Text, default=None)


class Product(UUIDPrimaryKey, Timestamped, SoftDelete, Sluggable, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_search", "search_vector", postgresql_using="gin"),
        Index("ix_products_category_published", "category_id", "is_published"),
    )

    title: Mapped[dict[str, Any]]
    description: Mapped[dict[str, Any]]
    highlights: Mapped[dict[str, Any]] = mapped_column(default=dict)

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id"), default=None)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    rating_average: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0"))
    rating_count: Mapped[int] = mapped_column(Integer, default=0)

    tags: Mapped[list[str]] = mapped_column(ARRAY(String(48)), default=list)

    # Generated column: Postgres keeps this in sync, so no code path can forget
    # to refresh the index. Swedish stemming is the base configuration because
    # the primary market is Sweden; English titles are folded into the same
    # vector and additionally covered by a trigram index (see migration 0002).
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('swedish', coalesce(title->>'sv','') || ' ' "
            "|| coalesce(title->>'en','') || ' ' || coalesce(description->>'sv',''))",
            persisted=True,
        ),
        nullable=True,
    )

    category: Mapped[Category] = relationship(lazy="joined")
    brand: Mapped[Brand | None] = relationship(lazy="joined")
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductImage.position",
    )

    @property
    def default_variant(self) -> ProductVariant | None:
        active = [v for v in self.variants if v.is_active]
        return min(active, key=lambda v: v.price_minor_units) if active else None


class ProductVariant(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_product_variants_sku"),
        CheckConstraint("price_minor_units >= 0", name="price_non_negative"),
        CheckConstraint(
            "compare_at_minor_units IS NULL OR compare_at_minor_units >= price_minor_units",
            name="compare_at_above_price",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(64))
    # Free-form axis map: {"colour": "granite", "size": "180"}. JSONB here
    # avoids an EAV table and the join storm that comes with it.
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)

    price_minor_units: Mapped[int] = mapped_column(Integer)
    compare_at_minor_units: Mapped[int | None] = mapped_column(Integer, default=None)
    currency: Mapped[str] = mapped_column(String(3), default="SEK")
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.250"))

    weight_grams: Mapped[int | None] = mapped_column(Integer, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    product: Mapped[Product] = relationship(back_populates="variants")


class ProductImage(UUIDPrimaryKey, Base):
    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[dict[str, Any]] = mapped_column(default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)

    product: Mapped[Product] = relationship(back_populates="images")
