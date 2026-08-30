"""Cursor pagination.

Offset pagination degrades badly once a catalogue passes a few hundred
thousand rows, and it double-shows or skips items when the underlying list
changes between pages. Every list endpoint here uses an opaque keyset cursor
instead: stable under concurrent writes and O(1) regardless of depth.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


def encode_cursor(payload: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload, default=str).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    padding = "=" * (-len(cursor) % 4)
    payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode(cursor + padding))
    return payload


@dataclass(slots=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None
    total: int | None = None


class PageMeta(BaseModel):
    next_cursor: str | None = None
    total: int | None = None


class PagedResponse[T](BaseModel):
    data: list[T]
    meta: PageMeta
