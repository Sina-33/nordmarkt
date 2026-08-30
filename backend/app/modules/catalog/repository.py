from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, decode_cursor, encode_cursor
from app.modules.catalog.models import Brand, Category, Product, ProductVariant


class ProductQuery:
    """Declarative description of a catalogue search.

    Kept separate from the repository so the same filter set can be reused by
    the HTTP layer, the sitemap generator and the merchandising admin without
    any of them assembling SQL by hand.
    """

    def __init__(
        self,
        *,
        search: str | None = None,
        category_path: str | None = None,
        brand_slugs: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
        min_price: int | None = None,
        max_price: int | None = None,
        in_stock_only: bool = False,
        sort: str = "relevance",
        limit: int = 24,
        cursor: str | None = None,
    ) -> None:
        self.search = search.strip() if search else None
        self.category_path = category_path
        self.brand_slugs = brand_slugs
        self.tags = tags
        self.min_price = min_price
        self.max_price = max_price
        self.in_stock_only = in_stock_only
        self.sort = sort
        self.limit = min(max(limit, 1), 60)
        self.cursor = cursor


_SORTS = {
    "relevance": (Product.created_at.desc(), Product.id.desc()),
    "newest": (Product.created_at.desc(), Product.id.desc()),
    "rating": (Product.rating_average.desc(), Product.id.desc()),
}


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    async def get_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(
            Product.slug == slug, Product.is_published.is_(True), Product.deleted_at.is_(None)
        )
        return await self._session.scalar(stmt)

    async def get_variant(self, variant_id: uuid.UUID) -> ProductVariant | None:
        return await self._session.get(ProductVariant, variant_id)

    async def get_variants(self, variant_ids: list[uuid.UUID]) -> dict[uuid.UUID, ProductVariant]:
        """Batch fetch. Called by cart and checkout to avoid an N+1 per line."""
        if not variant_ids:
            return {}
        stmt = select(ProductVariant).where(ProductVariant.id.in_(variant_ids))
        return {v.id: v for v in (await self._session.scalars(stmt)).all()}

    def _base_statement(self, query: ProductQuery) -> Select[Any]:
        stmt = (
            select(Product)
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .where(Product.is_published.is_(True), Product.deleted_at.is_(None))
            .distinct()
        )

        if query.search:
            # Two-pronged match: full-text for stemmed word matches, ILIKE as a
            # cheap prefix fallback so partial SKU and model-number lookups
            # still resolve.
            ts_query = func.websearch_to_tsquery("swedish", query.search)
            stmt = stmt.where(
                or_(
                    Product.search_vector.op("@@")(ts_query),
                    ProductVariant.sku.ilike(f"{query.search}%"),
                )
            )

        if query.category_path:
            stmt = stmt.join(Category, Category.id == Product.category_id).where(
                or_(
                    Category.path == query.category_path,
                    Category.path.startswith(f"{query.category_path}."),
                )
            )

        if query.brand_slugs:
            stmt = stmt.join(Brand, Brand.id == Product.brand_id).where(
                Brand.slug.in_(query.brand_slugs)
            )

        if query.tags:
            stmt = stmt.where(Product.tags.overlap(list(query.tags)))

        if query.min_price is not None:
            stmt = stmt.where(ProductVariant.price_minor_units >= query.min_price)
        if query.max_price is not None:
            stmt = stmt.where(ProductVariant.price_minor_units <= query.max_price)

        return stmt.where(ProductVariant.is_active.is_(True))

    async def search(self, query: ProductQuery) -> Page[Product]:
        stmt = self._base_statement(query)

        order_by = _SORTS.get(query.sort, _SORTS["relevance"])
        if query.cursor:
            marker = decode_cursor(query.cursor)
            # Keyset predicate on the same tuple the ORDER BY uses. Composite
            # comparison keeps it a single index range scan.
            stmt = stmt.where(
                or_(
                    Product.created_at < marker["created_at"],
                    and_(
                        Product.created_at == marker["created_at"],
                        Product.id < uuid.UUID(marker["id"]),
                    ),
                )
            )

        stmt = stmt.order_by(*order_by).limit(query.limit + 1)
        rows = list((await self._session.scalars(stmt)).unique().all())

        has_more = len(rows) > query.limit
        items = rows[: query.limit]
        next_cursor = (
            encode_cursor({"created_at": items[-1].created_at.isoformat(), "id": str(items[-1].id)})
            if has_more and items
            else None
        )
        return Page(items=items, next_cursor=next_cursor)

    async def count(self, query: ProductQuery) -> int:
        stmt = self._base_statement(query).with_only_columns(
            func.count(func.distinct(Product.id))
        ).order_by(None)
        return int(await self._session.scalar(stmt) or 0)

    async def price_bounds(self, query: ProductQuery) -> tuple[int, int]:
        stmt = (
            self._base_statement(query)
            .with_only_columns(
                func.min(ProductVariant.price_minor_units),
                func.max(ProductVariant.price_minor_units),
            )
            .order_by(None)
        )
        row = (await self._session.execute(stmt)).one()
        return int(row[0] or 0), int(row[1] or 0)

    async def brand_facets(self, query: ProductQuery) -> list[tuple[str, str, int]]:
        """Facet counts computed against the *unfaceted* result set.

        Counting with the brand filter already applied would leave every other
        brand at zero and make the filter panel useless after the first click.
        """
        unfiltered = ProductQuery(
            search=query.search,
            category_path=query.category_path,
            tags=query.tags,
            min_price=query.min_price,
            max_price=query.max_price,
        )
        stmt = (
            self._base_statement(unfiltered)
            .join(Brand, Brand.id == Product.brand_id)
            .with_only_columns(Brand.slug, Brand.name, func.count(func.distinct(Product.id)))
            .order_by(None)
            .group_by(Brand.slug, Brand.name)
            .order_by(func.count(func.distinct(Product.id)).desc())
        )
        return [(r[0], r[1], int(r[2])) for r in (await self._session.execute(stmt)).all()]


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def tree(self) -> list[Category]:
        stmt = select(Category).order_by(Category.path, Category.position)
        return list((await self._session.scalars(stmt)).all())

    async def by_path(self, path: str) -> Category | None:
        return await self._session.scalar(select(Category).where(Category.path == path))

    async def breadcrumb(self, path: str) -> list[Category]:
        """All ancestors plus the node itself, in one query."""
        segments = path.split(".")
        prefixes = [".".join(segments[: i + 1]) for i in range(len(segments))]
        stmt = select(Category).where(Category.path.in_(prefixes)).order_by(Category.depth)
        return list((await self._session.scalars(stmt)).all())
