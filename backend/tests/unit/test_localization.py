from app.shared.localization import negotiate_locale, resolve_translation
from app.shared.slugify import slugify


def test_falls_back_when_translation_missing() -> None:
    assert resolve_translation({"sv": "", "en": "Chair"}, "sv") == "Chair"


def test_prefers_requested_locale() -> None:
    assert resolve_translation({"sv": "Stol", "en": "Chair"}, "sv") == "Stol"


def test_accept_language_quality_ordering() -> None:
    header = "de;q=0.9, en;q=0.8, sv;q=1.0"
    assert negotiate_locale(header, ("sv", "en"), "sv") == "sv"


def test_unsupported_language_falls_back_to_default() -> None:
    assert negotiate_locale("ja, ko;q=0.5", ("sv", "en"), "en") == "en"


def test_swedish_characters_are_folded_not_stripped() -> None:
    assert slugify("Fåtölj Hedvig") == "fatolj-hedvig"
    assert slugify("Kök & Bord") == "kok-bord"
