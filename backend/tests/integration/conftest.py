"""Fixtures for the tests that need a live database.

Every test gets its own product, variant and stock row, keyed by a random
marker. Sharing a seeded variant between tests would make the concurrency
assertions depend on execution order, which is exactly the kind of flakiness
that makes people stop trusting a suite.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete

from app.db.session import dispose_engine, get_session_factory
from app.modules.catalog.models import Category, Product, ProductVariant
from app.modules.inventory.models import StockItem, StockReservation


@pytest.fixture(autouse=True)
async def _fresh_engine() -> AsyncIterator[None]:
    """Drop the cached engine between tests.

    ``get_engine`` memoises a single engine, and its asyncpg connections belong
    to the event loop that opened them. pytest-asyncio gives each test a new
    loop, so a pooled connection carried across would fail with "attached to a
    different loop".
    """
    yield
    await dispose_engine()


@pytest.fixture
async def seeded_variant_with_one_unit() -> AsyncIterator[uuid.UUID]:
    marker = uuid.uuid4().hex[:12]
    factory = get_session_factory()

    async with factory() as session:
        category = Category(
            slug=f"test-category-{marker}",
            name={"sv": "Testkategori", "en": "Test category"},
            path=f"test-{marker}",
        )
        session.add(category)
        await session.flush()

        product = Product(
            slug=f"test-product-{marker}",
            title={"sv": "Testprodukt", "en": "Test product"},
            description={"sv": "En testprodukt.", "en": "A test product."},
            category_id=category.id,
            is_published=True,
        )
        session.add(product)
        await session.flush()

        variant = ProductVariant(
            product_id=product.id,
            sku=f"TEST-{marker}",
            price_minor_units=19900,
        )
        session.add(variant)
        await session.flush()

        session.add(StockItem(variant_id=variant.id, on_hand=1, reserved=0))
        await session.commit()

        category_id, product_id, variant_id = category.id, product.id, variant.id

    yield variant_id

    async with factory() as session:
        await session.execute(
            delete(StockReservation).where(StockReservation.variant_id == variant_id)
        )
        await session.execute(delete(StockItem).where(StockItem.variant_id == variant_id))
        await session.execute(delete(ProductVariant).where(ProductVariant.id == variant_id))
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.execute(delete(Category).where(Category.id == category_id))
        await session.commit()
