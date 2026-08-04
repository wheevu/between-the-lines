"""Small, deterministic helpers for the edition ledger.

The ledger deliberately keeps hashes, bounded excerpts, and structured signals.
It does not need a copy of an article to show what changed or to bind a review
to the exact claim a reviewer saw. A caller may assert a hash for private full
source material while persisting only an excerpt. That assertion is format-
validated, but it can only be content-verified when the full source is supplied;
the stored excerpt always receives its own independently computed hash.
"""

import re
import unicodedata
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models import EditionDiffCategory, EditionDiffChange, EditionSignals

MAX_EXCERPT_LENGTH = 2_000

_NUMBER = re.compile(
    r"(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s?%)?(?!\w)"
)
_DATE = re.compile(
    r"(?:\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b|"
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b|"
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b|\b(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:no|not|never|neither|nor|without|cannot|can't|didn't|doesn't|"
    r"don't|won't|denied|reject(?:ed|s)?)\b|"
    r"(?:\bkhông\b|\bchưa\b|\bchẳng\b|\bkhông phải\b|"
    r"\bphủ nhận\b|\b안\b|\b못\b|\b않\w*\b|\b없\w*\b|\b부인\w*\b)",
    re.IGNORECASE,
)
_NAME = re.compile(
    r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,}"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]{1,})+\b"
)
_TOKEN = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "been",
    "before",
    "being",
    "between",
    "could",
    "from",
    "have",
    "into",
    "more",
    "only",
    "said",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "were",
    "which",
    "with",
    "would",
}


def canonicalize_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    parsed = urlsplit(raw_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return raw_url.strip()
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(sorted(query)),
            "",
        )
    )


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def validate_sha256(value: str, *, field_name: str = "SHA-256 value") -> str:
    """Validate and canonicalize a caller-supplied SHA-256 digest."""

    if not _SHA256.fullmatch(value):
        raise ValueError(f"{field_name} must be a 64-character hexadecimal SHA-256 digest.")
    return value.lower()


def normalized_claim_hash(text: str) -> str:
    return text_hash(normalize_text(text))


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


def bounded_excerpt(text: str, *, limit: int = MAX_EXCERPT_LENGTH) -> str:
    if limit < 1:
        return ""
    return text[:limit]


def extract_signals(text: str) -> EditionSignals:
    numbers = _ordered_unique(match.group(0).strip() for match in _NUMBER.finditer(text))
    dates = _ordered_unique(match.group(0).strip() for match in _DATE.finditer(text))
    negations = _ordered_unique(
        match.group(0).strip().casefold() for match in _NEGATION.finditer(text)
    )
    names = _ordered_unique(match.group(0).strip() for match in _NAME.finditer(text))
    terminology = sorted(
        {
            token.casefold()
            for token in _TOKEN.findall(unicodedata.normalize("NFKC", text))
            if len(token) >= 4
            and not token.isdigit()
            and token.casefold() not in _STOP_WORDS
        }
    )
    return EditionSignals(
        numbers=numbers,
        dates=dates,
        negations=negations,
        names=names,
        terminology=terminology,
    )


def diff_signals(before: EditionSignals, after: EditionSignals) -> list[EditionDiffChange]:
    pairs = (
        (EditionDiffCategory.NUMBER, before.numbers, after.numbers),
        (EditionDiffCategory.DATE, before.dates, after.dates),
        (EditionDiffCategory.NEGATION, before.negations, after.negations),
        (EditionDiffCategory.NAME, before.names, after.names),
        (EditionDiffCategory.TERMINOLOGY, before.terminology, after.terminology),
    )
    changes: list[EditionDiffChange] = []
    for category, old_values, new_values in pairs:
        old_by_key = {normalize_text(value): value for value in old_values}
        new_by_key = {normalize_text(value): value for value in new_values}
        removed = [old_by_key[key] for key in sorted(old_by_key.keys() - new_by_key.keys())]
        added = [new_by_key[key] for key in sorted(new_by_key.keys() - old_by_key.keys())]
        if removed or added:
            changes.append(
                EditionDiffChange(category=category, removed=removed, added=added)
            )
    return changes


def payload_hash(*parts: str) -> str:
    return text_hash("\n".join(parts))


def _ordered_unique(values: object) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_value in values:  # type: ignore[union-attr]
        value = str(raw_value)
        key = normalize_text(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result
