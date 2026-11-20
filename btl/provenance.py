"""Deterministic URL canonicalization, hashing, bounded excerpts, and edition diffing."""

from __future__ import annotations

import re
import unicodedata
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from btl.fact_guard import DATE_PATTERN, detect_legal_state, detect_modality
from btl.language import resolve_language
from btl.types import (
    EditionDiffCategory,
    EditionDiffChange,
    EditionDiffResult,
    EditionSignals,
    Language,
    LanguageOrAuto,
)

MAX_EXCERPT_LENGTH = 2_000

_NUMBER = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s?%)?(?!\w)")
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
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}

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


def canonicalize_url(raw_url: str | None, *, strict: bool = False) -> str | None:
    """Normalize HTTP(S) URLs, stripping tracking parameters and www prefixes."""
    if not raw_url:
        if strict:
            raise ValueError("URL must not be empty.")
        return None
    stripped = raw_url.strip()
    parsed = urlsplit(stripped)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        if strict:
            raise ValueError("URL must use HTTP or HTTPS with a valid hostname.")
        return stripped
    if strict and (parsed.username or parsed.password):
        raise ValueError("URL credentials are not allowed.")

    host = parsed.hostname.lower().removeprefix("www.")
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query), doseq=True), ""))


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


def normalized_claim_hash(text: str) -> str:
    return text_hash(normalize_text(text))


def bounded_excerpt(text: str, *, limit: int = MAX_EXCERPT_LENGTH) -> str:
    if limit < 1:
        return ""
    return text[:limit]


def extract_signals(text: str, language: Language | None = None) -> EditionSignals:
    """Extract deterministic factual signals across numbers, dates, negations, names, modality."""
    lang = language or resolve_language(text, "auto")
    numbers = _ordered_unique(match.group(0).strip() for match in _NUMBER.finditer(text))
    dates = _ordered_unique(match.group(0).strip() for match in DATE_PATTERN.finditer(text))
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
        modality=detect_modality(text, lang),
        legal_state=detect_legal_state(text, lang),
        terminology=terminology,
    )


def diff_signals(before: EditionSignals, after: EditionSignals) -> list[EditionDiffChange]:
    """Compare two EditionSignals objects and emit category-scoped deltas."""
    list_pairs = (
        (EditionDiffCategory.NUMBER, before.numbers, after.numbers),
        (EditionDiffCategory.DATE, before.dates, after.dates),
        (EditionDiffCategory.NEGATION, before.negations, after.negations),
        (EditionDiffCategory.NAME, before.names, after.names),
        (EditionDiffCategory.TERMINOLOGY, before.terminology, after.terminology),
    )
    changes: list[EditionDiffChange] = []
    for category, old_values, new_values in list_pairs:
        old_by_key = {normalize_text(value): value for value in old_values}
        new_by_key = {normalize_text(value): value for value in new_values}
        removed = [old_by_key[key] for key in sorted(old_by_key.keys() - new_by_key.keys())]
        added = [new_by_key[key] for key in sorted(new_by_key.keys() - old_by_key.keys())]
        if removed or added:
            changes.append(EditionDiffChange(category=category, removed=removed, added=added))

    if before.modality is not after.modality:
        changes.append(
            EditionDiffChange(
                category=EditionDiffCategory.MODALITY,
                removed=[before.modality.value],
                added=[after.modality.value],
            )
        )
    if before.legal_state is not after.legal_state:
        changes.append(
            EditionDiffChange(
                category=EditionDiffCategory.LEGAL_STATE,
                removed=[before.legal_state.value] if before.legal_state else [],
                added=[after.legal_state.value] if after.legal_state else [],
            )
        )
    return changes


def diff_editions(
    before_text: str,
    after_text: str,
    *,
    before_language: LanguageOrAuto = "auto",
    after_language: LanguageOrAuto = "auto",
) -> EditionDiffResult:
    """Compare two text editions and return structured deltas with SHA-256 provenance."""
    before_lang = resolve_language(before_text, before_language)
    after_lang = resolve_language(after_text, after_language)
    before_signals = extract_signals(before_text, before_lang)
    after_signals = extract_signals(after_text, after_lang)
    changes = diff_signals(before_signals, after_signals)
    before_sha = text_hash(before_text)
    after_sha = text_hash(after_text)
    return EditionDiffResult(
        changed=bool(changes) or before_sha != after_sha,
        before_language=before_lang,
        after_language=after_lang,
        before_sha256=before_sha,
        after_sha256=after_sha,
        changes=changes,
    )


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
