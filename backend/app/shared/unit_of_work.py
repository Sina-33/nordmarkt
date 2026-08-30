"""Unit of Work.

One HTTP request maps to one database transaction. Services take a UoW rather
than a session so they never call ``commit`` themselves - the boundary owns
that decision, which makes it trivial to compose two services inside a single
atomic operation (checkout touches cart, inventory and orders at once).

Domain events raised during the transaction are written to the outbox table in
the *same* commit. That is what makes "order created" and "confirmation email
queued" impossible to desynchronise: either both land or neither does.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.shared.events import DomainEvent
from app.shared.outbox import OutboxMessage


class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._events: list[DomainEvent] = []
        self.session: AsyncSession

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        self._events = []
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    def emit(self, event: DomainEvent) -> None:
        self._events.append(event)

    async def commit(self) -> None:
        for event in self._events:
            self.session.add(
                OutboxMessage(
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    event_type=event.event_type,
                    payload=event.to_payload(),
                )
            )
        self._events = []
        await self.session.commit()

    async def rollback(self) -> None:
        self._events = []
        await self.session.rollback()
