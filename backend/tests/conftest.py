from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "NM_DATABASE_URL", "postgresql+asyncpg://nordmarkt:nordmarkt@localhost:5432/nordmarkt_test"
)
os.environ.setdefault("NM_REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("NM_JWT_SECRET", "test-secret-value-that-is-long-enough-32")
os.environ.setdefault("NM_ENVIRONMENT", "ci")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
