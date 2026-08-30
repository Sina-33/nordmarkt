"""Outbox relay.

Drains ``outbox_messages`` and hands each event to its handlers. Runs as its
own process so a slow consumer never adds latency to a shopper's request.

Scaling is horizontal: SKIP LOCKED means N replicas partition the table
between them with no coordination service. Delivery is at-least-once, so every
handler must tolerate replay.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.shared.outbox import claim_batch, mark_failed, mark_published

logger = get_logger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]
HANDLERS: dict[str, list[Handler]] = {}


def on(event_type: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        HANDLERS.setdefault(event_type, []).append(fn)
        return fn

    return decorator


@on("order.placed")
async def send_order_confirmation(payload: dict[str, Any]) -> None:
    logger.info(
        "email_queued",
        template="order_confirmation",
        order_number=payload["order_number"],
        locale=payload.get("locale", "sv"),
    )


@on("order.paid")
async def notify_warehouse(payload: dict[str, Any]) -> None:
    logger.info("warehouse_notified", order_number=payload["order_number"])


@on("inventory.ran_low")
async def alert_merchandising(payload: dict[str, Any]) -> None:
    logger.info("restock_alert", variant_id=payload["variant_id"], remaining=payload["remaining"])


class Relay:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._stopping = asyncio.Event()

    def request_stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        factory = get_session_factory()
        logger.info("relay_started", batch=self._settings.outbox_batch_size)

        while not self._stopping.is_set():
            processed = 0
            async with factory() as session:
                messages = await claim_batch(session, self._settings.outbox_batch_size)
                for message in messages:
                    try:
                        for handler in HANDLERS.get(message.event_type, []):
                            await handler(message.payload)
                        await mark_published(session, message.id)
                        processed += 1
                    except Exception as exc:
                        logger.warning(
                            "relay_handler_failed",
                            event_type=message.event_type,
                            attempts=message.attempts,
                            error=str(exc),
                        )
                        await mark_failed(session, message, str(exc))
                await session.commit()

            if processed == 0:
                # Idle backoff so an empty queue does not spin the database.
                with_timeout = self._settings.outbox_poll_interval_seconds
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stopping.wait(), timeout=with_timeout)

        logger.info("relay_stopped")


async def main() -> None:
    configure_logging(debug=get_settings().debug)
    relay = Relay()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, relay.request_stop)

    await relay.run()


if __name__ == "__main__":
    asyncio.run(main())
