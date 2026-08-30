"""The test that justifies the inventory design.

Two shoppers race for the last unit. Exactly one must win. This is written as
an integration test on purpose - it is meaningless against a mocked session,
because the property being tested belongs to Postgres, not to Python.

Requires a live database: `docker compose up -d db` then `pytest -m integration`.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.errors import InsufficientStock
from app.db.session import get_session_factory
from app.modules.inventory.service import InventoryService
from app.shared.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


async def attempt_reserve(variant_id: uuid.UUID, quantity: int) -> bool:
    try:
        async with UnitOfWork(get_session_factory()) as uow:
            await InventoryService(uow).reserve(variant_id, quantity)
            await uow.commit()
        return True
    except InsufficientStock:
        return False


@pytest.mark.asyncio
async def test_only_one_shopper_gets_the_last_unit(seeded_variant_with_one_unit) -> None:  # noqa: ANN001
    variant_id = seeded_variant_with_one_unit

    results = await asyncio.gather(
        *(attempt_reserve(variant_id, 1) for _ in range(8)), return_exceptions=False
    )

    assert sum(results) == 1, "exactly one reservation must succeed"


@pytest.mark.asyncio
async def test_released_reservation_returns_stock(seeded_variant_with_one_unit) -> None:  # noqa: ANN001
    variant_id = seeded_variant_with_one_unit

    async with UnitOfWork(get_session_factory()) as uow:
        service = InventoryService(uow)
        reservation = await service.reserve(variant_id, 1)
        await uow.commit()

    assert await attempt_reserve(variant_id, 1) is False

    async with UnitOfWork(get_session_factory()) as uow:
        service = InventoryService(uow)
        await service.release(await uow.session.get(type(reservation), reservation.id))
        await uow.commit()

    assert await attempt_reserve(variant_id, 1) is True
