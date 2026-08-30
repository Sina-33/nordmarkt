import re
import unicodedata

_TRANSLITERATE = str.maketrans({"å": "a", "ä": "a", "ö": "o", "é": "e", "ü": "u", "ø": "o"})


def slugify(value: str, *, max_length: int = 120) -> str:
    """Slugify with Swedish characters folded rather than dropped.

    Naive NFKD stripping turns "Fåtölj" into "Ftlj". Folding first keeps the
    URL readable, which matters for both shoppers and search engines.
    """
    lowered = value.strip().lower().translate(_TRANSLITERATE)
    normalised = unicodedata.normalize("NFKD", lowered)
    ascii_only = normalised.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug[:max_length].rstrip("-")
