from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Everything is read from the environment so the same image runs in every
    stage. Nothing here has a production-safe default on purpose: if a secret
    is missing the process refuses to boot instead of running insecurely.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NM_", extra="ignore")

    environment: Literal["local", "ci", "staging", "production"] = "local"
    debug: bool = False

    database_url: PostgresDsn
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_statement_timeout_ms: int = 5_000

    redis_url: RedisDsn

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30

    default_locale: str = "sv"
    supported_locales: tuple[str, ...] = ("sv", "en")
    default_currency: str = "SEK"

    cors_origins: tuple[str, ...] = ("http://localhost:3000",)

    outbox_batch_size: int = 100
    outbox_poll_interval_seconds: float = 1.0

    @property
    def sync_database_url(self) -> str:
        return str(self.database_url).replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
