"""Offset-preserving multilingual chunking and top-K passage ranking."""

from __future__ import annotations

import re
import unicodedata
from hashlib import sha256
from urllib.parse import urlsplit

from btl.embeddings import LocalEmbedder
from btl.fact_guard import extract_number_anchors
from btl.language import normalize_article, resolve_language, segment_article
from btl.lineage import near_duplicate_text
from btl.provenance import canonicalize_url, text_hash
from btl.types import (
    DocumentInput,
    ExtractRankResult,
    Language,
    LanguageOrAuto,
    RankedExcerpt,
    RetrievalFailure,
)

WORD_TOKENS = re.compile(r"[^\W_]+", re.UNICODE)


def chunk_document(
    doc: DocumentInput,
    *,
    target_words: int = 170,
    max_words: int = 220,
) -> list[dict[str, object]]:
    """Split a normalized document into sentence-aligned chunks with exact character offsets."""
    normalized = normalize_article(doc.text)
    if not normalized:
        return []
    lang = resolve_language(normalized, doc.language)
    segments = segment_article(normalized, lang)
    if not segments:
        return []

    chunks: list[list] = []
    current: list = []
    current_words = 0
    for seg in segments:
        seg_words = len(seg.text.split())
        if current and (current_words >= target_words or current_words + seg_words > max_words):
            chunks.append(current)
            current = []
            current_words = 0
        current.append(seg)
        current_words += seg_words
    if current:
        if chunks and sum(len(s.text.split()) for s in current) < 120:
            prev_words = sum(len(s.text.split()) for s in chunks[-1])
            if prev_words + current_words <= max_words:
                chunks[-1].extend(current)
            else:
                chunks.append(current)
        else:
            chunks.append(current)

    canonical_url = canonicalize_url(doc.url) if doc.url else None
    publisher = (
        doc.publisher.strip()
        if doc.publisher and doc.publisher.strip()
        else _publisher_from_url(canonical_url)
    )
    built: list[dict[str, object]] = []
    for chunk_segments in chunks:
        char_start = chunk_segments[0].start_offset
        char_end = chunk_segments[-1].end_offset
        excerpt = normalized[char_start:char_end]
        built.append(
            {
                "url": doc.url,
                "canonical_url": canonical_url,
                "title": doc.title,
                "publisher": publisher,
                "language": lang,
                "published_at_unverified": doc.published_at,
                "excerpt": excerpt,
                "char_start": char_start,
                "char_end": char_end,
                "content_hash": text_hash(excerpt),
            }
        )
    return built


def extract_and_rank(
    claim: str,
    documents: list[DocumentInput],
    *,
    claim_language: LanguageOrAuto = "auto",
    failures: list[RetrievalFailure] | None = None,
    limit: int = 6,
    per_publisher: int = 2,
    max_candidates: int = 80,
    embedder: LocalEmbedder | None = None,
    use_embeddings: bool = True,
) -> ExtractRankResult:
    """Chunk, deduplicate, and rank excerpts from extracted or pre-fetched documents."""
    resolved_claim_lang = resolve_language(claim, claim_language)
    raw_chunks: list[dict[str, object]] = []
    for doc in documents:
        raw_chunks.extend(chunk_document(doc))
        if len(raw_chunks) >= max_candidates:
            raw_chunks = raw_chunks[:max_candidates]
            break

    if not raw_chunks or limit <= 0:
        return ExtractRankResult(
            claim=claim,
            claim_language=resolved_claim_lang,
            embeddings_used=False,
            documents_processed=len(documents),
            excerpts=[],
            failures=list(failures or []),
        )

    cluster_history: list[tuple[str, str]] = []
    candidates: list[dict[str, object]] = []
    for idx, chunk in enumerate(raw_chunks):
        excerpt = str(chunk["excerpt"])
        content_hash = str(chunk["content_hash"])
        cluster_id = _assign_cluster(excerpt, content_hash, cluster_history)
        cluster_history.append((cluster_id, excerpt))
        source_key = str(chunk["canonical_url"] or chunk["publisher"] or f"doc-{idx}")
        digest = sha256(f"{source_key}\0{idx}\0{excerpt}".encode()).hexdigest()[:12]
        candidates.append(
            {
                **chunk,
                "excerpt_id": f"excerpt-{digest}",
                "cluster_id": cluster_id,
            }
        )

    embeddings_used = False
    scoring_method = "lexical"
    scores: list[float] | None = None
    if use_embeddings and embedder is not None:
        try:
            scores = embedder.similarities(
                [claim] * len(candidates),
                [str(item["excerpt"]) for item in candidates],
            )
            embeddings_used = True
            scoring_method = "e5"
        except Exception:
            scores = None

    if scores is None:
        scores = [
            _lexical_score(
                claim,
                resolved_claim_lang,
                str(item["excerpt"]),
                item["language"],  # type: ignore[arg-type]
            )
            for item in candidates
        ]

    ranked = sorted(
        zip(candidates, scores, strict=True),
        key=lambda pair: pair[1],
        reverse=True,
    )

    selected: list[RankedExcerpt] = []
    publisher_counts: dict[str, int] = {}
    seen_clusters: set[str] = set()
    for item, score in ranked:
        publisher = str(item["publisher"])
        cluster_id = str(item["cluster_id"])
        if publisher_counts.get(publisher, 0) >= per_publisher:
            continue
        if cluster_id in seen_clusters:
            continue
        selected.append(
            RankedExcerpt(
                excerpt_id=str(item["excerpt_id"]),
                url=item["url"],  # type: ignore[arg-type]
                canonical_url=item["canonical_url"],  # type: ignore[arg-type]
                title=item["title"],  # type: ignore[arg-type]
                publisher=publisher,
                language=item["language"],  # type: ignore[arg-type]
                published_at_unverified=item["published_at_unverified"],  # type: ignore[arg-type]
                excerpt=str(item["excerpt"]),
                char_start=int(item["char_start"]),  # type: ignore[arg-type]
                char_end=int(item["char_end"]),  # type: ignore[arg-type]
                content_hash=str(item["content_hash"]),
                cluster_id=cluster_id,
                relevance=round(float(score), 4),
                scoring_method=scoring_method,  # type: ignore[arg-type]
            )
        )
        publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
        seen_clusters.add(cluster_id)
        if len(selected) == limit:
            break

    return ExtractRankResult(
        claim=claim,
        claim_language=resolved_claim_lang,
        embeddings_used=embeddings_used,
        documents_processed=len(documents),
        excerpts=selected,
        failures=list(failures or []),
    )


def _assign_cluster(
    excerpt: str,
    fallback: str,
    previous: list[tuple[str, str]],
) -> str:
    for cluster_id, other in previous:
        if near_duplicate_text(excerpt, other):
            return cluster_id
    return f"cluster-{fallback[:12]}"


def _lexical_score(
    claim: str,
    claim_lang: Language,
    excerpt: str,
    excerpt_lang: Language,
) -> float:
    claim_tokens = _tokens(claim)
    excerpt_tokens = _tokens(excerpt)
    token_score = (
        len(claim_tokens & excerpt_tokens) / max(1, len(claim_tokens))
        if claim_tokens
        else 0.0
    )
    claim_anchors = extract_number_anchors(claim, claim_lang)
    excerpt_anchors = extract_number_anchors(excerpt, excerpt_lang)
    anchor_score = (
        len(claim_anchors & excerpt_anchors) / max(1, len(claim_anchors))
        if claim_anchors
        else 0.0
    )
    if claim_anchors:
        return round(0.6 * token_score + 0.4 * anchor_score, 4)
    return round(token_score, 4)


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return {tok for tok in WORD_TOKENS.findall(normalized) if len(tok) >= 2}


def _publisher_from_url(url: str | None) -> str:
    if not url:
        return "local-document"
    host = urlsplit(url).hostname
    return host.lower().removeprefix("www.") if host else "local-document"
