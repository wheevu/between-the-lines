"""Cross-script wire/origin alias clustering and near-duplicate deduplication."""

from __future__ import annotations

import re
import unicodedata
from hashlib import sha256
from itertools import combinations
from typing import Protocol

from btl.language import resolve_language
from btl.provenance import canonicalize_url
from btl.types import (
    Language,
    OriginCluster,
    OriginClusterResult,
    OriginInputItem,
)

WHITESPACE = re.compile(r"\s+")
WORDS = re.compile(r"\w+", re.UNICODE)
UPPERCASE_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
LATIN_WORD = re.compile(r"[A-Za-z]+")
ORIGIN_SIMILARITY_THRESHOLD = 0.94

# Canonical alias groups spanning English, Vietnamese, and Korean wire services,
# major international outlets, and recurring public institutions.
CANONICAL_ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "Reuters": ("reuters", "로이터", "로이터통신", "hãng tin reuters"),
    "Associated Press": ("associated press", "ap", "ap news", "ap통신", "hãng tin ap"),
    "AFP": ("afp", "agence france-presse", "afp통신", "hãng tin afp"),
    "Bloomberg": ("bloomberg", "bloomberg news", "블룸버그", "블룸버그통신"),
    "Yonhap News Agency": (
        "yonhap",
        "yonhap news",
        "yonhap news agency",
        "연합뉴스",
        "hãng thông tấn yonhap",
    ),
    "Kyodo News": ("kyodo", "kyodo news", "교도통신", "hãng tin kyodo"),
    "Vietnam News Agency": ("vietnam news agency", "vna", "ttxvn", "thông tấn xã việt nam"),
    "BBC": ("bbc", "bbc news", "bbc tiếng việt", "영국 bbc"),
    "World Meteorological Organization": (
        "world meteorological organization",
        "wmo",
        "세계기상기구",
        "tổ chức khí tượng thế giới",
    ),
    "World Health Organization": (
        "world health organization",
        "who",
        "세계보건기구",
        "tổ chức y tế thế giới",
    ),
    "International Monetary Fund": (
        "international monetary fund",
        "imf",
        "국제통화기금",
        "quỹ tiền tệ quốc tế",
    ),
    "OECD": ("oecd", "경제협력개발기구", "tổ chức hợp tác và phát triển kinh tế"),
    "Statistics Korea": ("statistics korea", "kostat", "통계청"),
    "General Statistics Office": ("general statistics office", "gso", "tổng cục thống kê"),
    "Government of Vietnam": (
        "government of vietnam",
        "chính phủ việt nam",
        "cổng thông tin điện tử chính phủ",
        "chinhphu.vn",
    ),
    "Ministry of Education and Training (Vietnam)": (
        "ministry of education and training",
        "moet",
        "bộ giáo dục và đào tạo",
    ),
    "Ministry of Education (Korea)": ("ministry of education", "교육부"),
}

_ALIAS_LOOKUP: dict[str, str] = {
    " ".join(unicodedata.normalize("NFKC", alias).casefold().split()): canonical
    for canonical, aliases in CANONICAL_ALIAS_GROUPS.items()
    for alias in aliases
}


class SimilarityProvider(Protocol):
    def similarities(self, left: list[str], right: list[str]) -> list[float]: ...


def near_duplicate_text(first: str, second: str) -> bool:
    """Return True when two excerpts are textual near-duplicates."""
    tokens_a = set(WORDS.findall(first.lower()))
    tokens_b = set(WORDS.findall(second.lower()))
    if not tokens_a or not tokens_b:
        return False
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    containment = len(intersection) / min(len(tokens_a), len(tokens_b))
    jaccard = len(intersection) / len(union) if union else 0.0
    return containment >= 0.9 and jaccard >= 0.6


def resolve_alias_canonical(origin: str) -> str | None:
    """Resolve an origin string against the curated EN/VI/KO alias table."""
    norm = _normalize(origin)
    if norm in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[norm]
    stripped = re.sub(r"\([^)]*\)", "", norm).strip()
    if stripped in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[stripped]
    for match in UPPERCASE_ACRONYM.finditer(origin):
        acro = match.group(0).casefold()
        if acro in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[acro]
    return None


def cluster_origins(
    items: list[OriginInputItem],
    *,
    embedder: SimilarityProvider | None = None,
    use_embeddings: bool = False,
) -> OriginClusterResult:
    """Group multi-language items by credited origin, aliases, acronyms, and near-duplicates."""
    if not items:
        return OriginClusterResult(
            source_count=0,
            independent_lineage_count=0,
            syndication_collapsed=0,
            embeddings_used=False,
            clusters=[],
        )

    n = len(items)
    parents = list(range(n))
    merge_basis: dict[int, set[str]] = {i: set() for i in range(n)}

    def root(idx: int) -> int:
        while parents[idx] != idx:
            parents[idx] = parents[parents[idx]]
            idx = parents[idx]
        return idx

    def union(a: int, b: int, basis: str) -> None:
        ra, rb = root(a), root(b)
        if ra == rb:
            merge_basis[ra].add(basis)
            return
        if ra > rb:
            ra, rb = rb, ra
        parents[rb] = ra
        merge_basis[ra].update(merge_basis[rb])
        merge_basis[ra].add(basis)

    canonical_urls = [canonicalize_url(item.url) if item.url else None for item in items]
    resolved_aliases = [
        resolve_alias_canonical(item.credited_origin) if item.credited_origin else None
        for item in items
    ]
    acronyms = [
        _origin_aliases(item.credited_origin) if item.credited_origin else set()
        for item in items
    ]

    embedding_pairs: list[tuple[int, int]] = []
    for i, j in combinations(range(n), 2):
        if canonical_urls[i] and canonical_urls[i] == canonical_urls[j]:
            union(i, j, "url")
            continue
        oi = items[i].credited_origin
        oj = items[j].credited_origin
        if oi and oj:
            if _normalize(oi) == _normalize(oj):
                union(i, j, "exact")
                continue
            if resolved_aliases[i] and resolved_aliases[i] == resolved_aliases[j]:
                union(i, j, "alias")
                continue
            if acronyms[i] & acronyms[j]:
                union(i, j, "acronym")
                continue
            if use_embeddings and embedder is not None:
                embedding_pairs.append((i, j))
        ei = items[i].excerpt
        ej = items[j].excerpt
        if ei and ej and near_duplicate_text(ei, ej):
            union(i, j, "near_duplicate")

    embeddings_used = False
    if embedding_pairs and embedder is not None:
        left = [items[i].credited_origin or "" for i, _ in embedding_pairs]
        right = [items[j].credited_origin or "" for _, j in embedding_pairs]
        try:
            scores = embedder.similarities(left, right)
            embeddings_used = True
            for (i, j), score in zip(embedding_pairs, scores, strict=True):
                if score >= ORIGIN_SIMILARITY_THRESHOLD:
                    union(i, j, "embedding")
        except Exception:
            embeddings_used = False

    groups: dict[int, list[int]] = {}
    for idx in range(n):
        groups.setdefault(root(idx), []).append(idx)

    clusters: list[OriginCluster] = []
    for root_idx, member_indices in groups.items():
        origins_seen = list(
            dict.fromkeys(
                items[idx].credited_origin.strip()
                for idx in member_indices
                if items[idx].credited_origin and items[idx].credited_origin.strip()
            )
        )
        canonical_label = _pick_canonical_label(
            member_indices, items, resolved_aliases, canonical_urls
        )
        basis_set = merge_basis[root_idx]
        basis = _pick_basis(basis_set, bool(origins_seen))
        member_ids = [items[idx].id or f"src-{idx + 1}" for idx in member_indices]
        urls = list(
            dict.fromkeys(
                url
                for idx in member_indices
                if (url := canonical_urls[idx]) is not None
            )
        )
        langs = sorted(
            {
                resolve_language(
                    items[idx].excerpt or items[idx].title or items[idx].credited_origin or "",
                    items[idx].language,
                )
                for idx in member_indices
            },
            key=lambda lang: list(Language).index(lang),
        )
        digest = sha256(
            "|".join(sorted(origins_seen or urls or member_ids)).encode()
        ).hexdigest()[:12]
        lineage_prefix = "lineage" if origins_seen or len(member_indices) > 1 else "article"
        clusters.append(
            OriginCluster(
                lineage_id=f"{lineage_prefix}-{digest}",
                canonical_origin=canonical_label,
                basis=basis,
                independence_hint=(
                    "resolved-shared" if len(member_indices) > 1 else "resolved-independent"
                ),
                member_ids=member_ids,
                urls=urls,
                languages=langs,
                origins_seen=origins_seen,
            )
        )

    return OriginClusterResult(
        source_count=n,
        independent_lineage_count=len(clusters),
        syndication_collapsed=max(0, n - len(clusters)),
        embeddings_used=embeddings_used,
        clusters=clusters,
    )


def _pick_canonical_label(
    indices: list[int],
    items: list[OriginInputItem],
    resolved_aliases: list[str | None],
    canonical_urls: list[str | None],
) -> str:
    for idx in indices:
        if resolved_aliases[idx]:
            return resolved_aliases[idx]  # type: ignore[return-value]
    for idx in indices:
        if items[idx].credited_origin and items[idx].credited_origin.strip():
            return items[idx].credited_origin.strip()
    for idx in indices:
        if items[idx].publisher.strip():
            return items[idx].publisher.strip()
    for idx in indices:
        if canonical_urls[idx]:
            return canonical_urls[idx]  # type: ignore[return-value]
    return items[indices[0]].id or f"src-{indices[0] + 1}"


def _pick_basis(
    basis_set: set[str], has_origin: bool
) -> str:
    for candidate in ("alias", "acronym", "exact", "embedding", "near_duplicate", "url"):
        if candidate in basis_set:
            return candidate
    return "exact" if has_origin else "url"


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return WHITESPACE.sub(" ", normalized).strip()


def _origin_aliases(value: str) -> set[str]:
    aliases = {match.group(0) for match in UPPERCASE_ACRONYM.finditer(value)}
    latin_words = LATIN_WORD.findall(value)
    if len(latin_words) >= 2:
        aliases.add("".join(word[0] for word in latin_words).upper())
    return aliases
