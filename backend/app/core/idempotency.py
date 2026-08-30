"""Idempotency keys for unsafe operations.

Checkout is the classic double-submit surface: the shopper taps Pay, the
connection drops, the app retries. Without this the customer is charged twice.
The key is claimed in Redis with SET NX; a completed response is cached so the
retry replays the original result rather than creating a second order.
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.core.errors import IdempotencyConflict

_CLAIM_TTL = 60 * 10
_RESULT_TTL = 60 * 60 * 24


class IdempotencyStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(scope: str, key: str) -> str:
        return f"idem:{scope}:{key}"

    async def claim(self, scope: str, key: str) -> dict[str, Any] | None:
        """Claim the key. Returns a cached result if this request already ran."""
        redis_key = self._key(scope, key)
        acquired = await self._redis.set(redis_key, "in_progress", nx=True, ex=_CLAIM_TTL)
        if acquired:
            return None
        stored = await self._redis.get(redis_key)
        if stored in (None, b"in_progress", "in_progress"):
            raise IdempotencyConflict("a request with this key is still in progress")
        return json.loads(stored)

    async def complete(self, scope: str, key: str, result: dict[str, Any]) -> None:
        await self._redis.set(self._key(scope, key), json.dumps(result, default=str), ex=_RESULT_TTL)

    async def release(self, scope: str, key: str) -> None:
        await self._redis.delete(self._key(scope, key))
