"""Localisation primitives.

Nordmarkt ships Swedish first and English second, so translated content is a
first-class column type rather than a bolted-on table. ``TranslatedText`` is a
JSONB map of locale -> string with deterministic fallback, which keeps a
product row to a single fetch instead of a join per language.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

Locale = Annotated[str, Field(pattern=r"^(sv|en)$")]

FALLBACK_CHAIN: dict[str, tuple[str, ...]] = {
    "sv": ("sv", "en"),
    "en": ("en", "sv"),
}


class TranslatedText(BaseModel):
    sv: str
    en: str

    def resolve(self, locale: str) -> str:
        for candidate in FALLBACK_CHAIN.get(locale, ("sv", "en")):
            value: str | None = getattr(self, candidate, None)
            if value:
                return value
        return ""


def resolve_translation(raw: dict[str, Any] | None, locale: str) -> str:
    if not raw:
        return ""
    for candidate in FALLBACK_CHAIN.get(locale, ("sv", "en")):
        if value := raw.get(candidate):
            return str(value)
    return next((str(v) for v in raw.values() if v), "")


def negotiate_locale(header: str | None, supported: tuple[str, ...], default: str) -> str:
    """Minimal RFC 7231 Accept-Language negotiation."""
    if not header:
        return default
    ranked: list[tuple[float, str]] = []
    for part in header.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        tag, _, params = chunk.partition(";")
        quality = 1.0
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        ranked.append((quality, tag.strip().lower().split("-")[0]))
    for _, tag in sorted(ranked, key=lambda item: item[0], reverse=True):
        if tag in supported:
            return tag
    return default
