"""Releases stock held by checkouts that were never completed."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.modules.inventory.service import InventoryService
from app.shared.unit_of_work import UnitOfWork

logger = get_logger(__name__)
INTERVAL_SECONDS = 60


async def sweep_once() -> int:
    async with UnitOfWork(get_session_factory()) as uow:
        released = await InventoryService(uow).release_expired()
        await uow.commit()
    return released


async def main() -> None:
    configure_logging(debug=get_settings().debug)
    logger.info("sweeper_started", interval=INTERVAL_SECONDS)
    while True:
        try:
            await sweep_once()
        except Exception:
            logger.exception("sweep_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
