from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import Money
from app.shared.localization import resolve_translation


class MoneyOut(BaseModel):
    amount: Decimal
    minor_units: int
    currency: str
    formatted: str

    @classmethod
    def of(cls, minor_units: int, currency: str, locale: str) -> MoneyOut:
        money = Money(minor_units, currency)
        return cls(
            amount=money.to_decimal(),
            minor_units=minor_units,
            currency=currency,
            formatted=format_money(money, locale),
        )


def format_money(money: Money, locale: str) -> str:
    """Locale-aware formatting.

    Sweden writes ``1 299,00 kr`` with a non-breaking thin space as the group
    separator and the symbol trailing; English writes ``SEK 1,299.00``. Getting
    this wrong is the fastest way to look foreign to a Swedish shopper.
    """
    value = money.to_decimal()
    if locale == "sv":
        whole, _, fraction = f"{value:,.2f}".partition(".")
        grouped = whole.replace(",", "\u00a0")
        symbol = {"SEK": "kr", "EUR": "€", "USD": "$"}.get(money.currency, money.currency)
        return f"{grouped},{fraction}\u00a0{symbol}"
    return f"{money.currency} {value:,.2f}"


class ImageOut(BaseModel):
    url: str
    alt: str
    width: int | None = None
    height: int | None = None


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    options: dict[str, str]
    price: MoneyOut
    compare_at: MoneyOut | None = None
    is_active: bool
    sellable: int | None = None


class ProductSummaryOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    brand: str | None
    price_from: MoneyOut
    compare_at: MoneyOut | None
    image: ImageOut | None
    rating_average: Decimal
    rating_count: int
    tags: list[str]


class ProductDetailOut(ProductSummaryOut):
    description: str
    highlights: list[str]
    category_path: str
    images: list[ImageOut]
    variants: list[VariantOut]


class BreadcrumbOut(BaseModel):
    slug: str
    path: str
    name: str


class CategoryOut(BaseModel):
    slug: str
    path: str
    name: str
    depth: int
    children: list[CategoryOut] = Field(default_factory=list)


class BrandFacetOut(BaseModel):
    slug: str
    name: str
    count: int


class FacetsOut(BaseModel):
    brands: list[BrandFacetOut]
    price_min: MoneyOut
    price_max: MoneyOut


class ProductListOut(BaseModel):
    data: list[ProductSummaryOut]
    facets: FacetsOut
    meta: dict[str, object]


def to_summary(product, locale: str) -> ProductSummaryOut:  # noqa: ANN001
    variant = product.default_variant
    image = product.images[0] if product.images else None
    return ProductSummaryOut(
        id=product.id,
        slug=product.slug,
        title=resolve_translation(product.title, locale),
        brand=product.brand.name if product.brand else None,
        price_from=MoneyOut.of(
            variant.price_minor_units if variant else 0,
            variant.currency if variant else "SEK",
            locale,
        ),
        compare_at=(
            MoneyOut.of(variant.compare_at_minor_units, variant.currency, locale)
            if variant and variant.compare_at_minor_units
            else None
        ),
        image=(
            ImageOut(
                url=image.url,
                alt=resolve_translation(image.alt_text, locale),
                width=image.width,
                height=image.height,
            )
            if image
            else None
        ),
        rating_average=product.rating_average,
        rating_count=product.rating_count,
        tags=list(product.tags or []),
    )


def to_detail(product, locale: str, stock: dict[uuid.UUID, int]) -> ProductDetailOut:  # noqa: ANN001
    summary = to_summary(product, locale)
    highlights = product.highlights.get(locale) or product.highlights.get("sv") or []
    return ProductDetailOut(
        **summary.model_dump(),
        description=resolve_translation(product.description, locale),
        highlights=list(highlights),
        category_path=product.category.path,
        images=[
            ImageOut(
                url=i.url,
                alt=resolve_translation(i.alt_text, locale),
                width=i.width,
                height=i.height,
            )
            for i in product.images
        ],
        variants=[
            VariantOut(
                id=v.id,
                sku=v.sku,
                options=v.options,
                price=MoneyOut.of(v.price_minor_units, v.currency, locale),
                compare_at=(
                    MoneyOut.of(v.compare_at_minor_units, v.currency, locale)
                    if v.compare_at_minor_units
                    else None
                ),
                is_active=v.is_active,
                sellable=stock.get(v.id, 0),
            )
            for v in product.variants
            if v.is_active
        ],
    )
