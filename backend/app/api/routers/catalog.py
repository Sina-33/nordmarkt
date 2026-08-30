from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import InventoryDep, LocaleDep, UoWDep
from app.core.errors import NotFound
from app.modules.catalog.repository import CategoryRepository, ProductQuery, ProductRepository
from app.modules.catalog.schemas import (
    BrandFacetOut,
    BreadcrumbOut,
    CategoryOut,
    FacetsOut,
    MoneyOut,
    ProductDetailOut,
    ProductListOut,
    to_detail,
    to_summary,
)
from app.shared.localization import resolve_translation

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=ProductListOut)
async def list_products(
    uow: UoWDep,
    locale: LocaleDep,
    response: Response,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=200)] = None,
    brand: Annotated[list[str] | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    sort: Annotated[str, Query(pattern="^(relevance|newest|rating)$")] = "relevance",
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
    cursor: str | None = None,
) -> ProductListOut:
    repo = ProductRepository(uow.session)
    query = ProductQuery(
        search=q,
        category_path=category,
        brand_slugs=tuple(brand or ()),
        tags=tuple(tag or ()),
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )

    page = await repo.search(query)
    total = await repo.count(query)
    facet_rows = await repo.brand_facets(query)
    low, high = await repo.price_bounds(query)

    # Catalogue listings are the hottest read path and change slowly. A short
    # shared TTL plus stale-while-revalidate lets the CDN absorb traffic spikes
    # without ever serving a shopper a spinner.
    response.headers["Cache-Control"] = "public, s-maxage=60, stale-while-revalidate=300"

    return ProductListOut(
        data=[to_summary(p, locale) for p in page.items],
        facets=FacetsOut(
            brands=[BrandFacetOut(slug=s, name=n, count=c) for s, n, c in facet_rows],
            price_min=MoneyOut.of(low, "SEK", locale),
            price_max=MoneyOut.of(high, "SEK", locale),
        ),
        meta={"next_cursor": page.next_cursor, "total": total, "locale": locale},
    )


@router.get("/products/{slug}", response_model=ProductDetailOut)
async def get_product(
    slug: str,
    uow: UoWDep,
    locale: LocaleDep,
    inventory: InventoryDep,
    response: Response,
) -> ProductDetailOut:
    product = await ProductRepository(uow.session).get_by_slug(slug)
    if product is None:
        raise NotFound("product not found", slug=slug)

    stock = await inventory.sellable_map([v.id for v in product.variants])
    response.headers["Cache-Control"] = "public, s-maxage=30, stale-while-revalidate=120"
    return to_detail(product, locale, stock)


@router.get("/categories", response_model=list[CategoryOut])
async def category_tree(uow: UoWDep, locale: LocaleDep) -> list[CategoryOut]:
    rows = await CategoryRepository(uow.session).tree()

    nodes: dict[str, CategoryOut] = {}
    roots: list[CategoryOut] = []
    for row in rows:
        node = CategoryOut(
            slug=row.slug,
            path=row.path,
            name=resolve_translation(row.name, locale),
            depth=row.depth,
        )
        nodes[row.path] = node
        parent_path = row.path.rsplit(".", 1)[0]
        if row.depth == 0 or parent_path not in nodes:
            roots.append(node)
        else:
            nodes[parent_path].children.append(node)
    return roots


@router.get("/categories/{path}/breadcrumb", response_model=list[BreadcrumbOut])
async def breadcrumb(path: str, uow: UoWDep, locale: LocaleDep) -> list[BreadcrumbOut]:
    rows = await CategoryRepository(uow.session).breadcrumb(path)
    if not rows:
        raise NotFound("category not found", path=path)
    return [
        BreadcrumbOut(slug=r.slug, path=r.path, name=resolve_translation(r.name, locale))
        for r in rows
    ]
