"""Deterministic facet extraction, claim grounding, and query-anchor verification."""

from __future__ import annotations

import re
import unicodedata

from btl.fact_guard import (
    DATE_PATTERN,
    detect_legal_state,
    detect_modality,
    extract_number_anchors,
    extract_ordered_numbers,
    has_attribution,
    has_future_plan,
    has_negation,
    has_uncertainty,
)
from btl.language import resolve_language, segment_article
from btl.types import (
    AnalyzeClaimsResult,
    ClaimFacetReport,
    ClaimGroundingCheck,
    ClaimInput,
    Language,
    LanguageOrAuto,
    QueryAnchorCheck,
    SearchQueryInput,
)


def extract_facets(text: str, language: Language | None = None) -> ClaimFacetReport:
    """Compute deterministic linguistic and factual facets for EN/VI/KO text."""
    lang = language or resolve_language(text, "auto")
    dates = list(dict.fromkeys(match.group(0).strip() for match in DATE_PATTERN.finditer(text)))
    return ClaimFacetReport(
        language=lang,
        modality=detect_modality(text, lang),
        legal_state=detect_legal_state(text, lang),
        has_negation=has_negation(text, lang),
        has_attribution=has_attribution(text, lang),
        numbers=extract_ordered_numbers(text, lang),
        dates=dates,
    )


def verify_claim_grounding(
    claim: ClaimInput,
    *,
    full_text: str,
    segment_by_id: dict[str, str],
    language: Language,
    index: int = 1,
) -> ClaimGroundingCheck:
    """Verify a candidate claim stays grounded in supplied source segments."""
    claim_id = claim.id or f"claim-{index}"
    reasons: list[str] = []

    if len(claim.source_quote) > 1_200:
        reasons.append("source_quote exceeds 1200 characters")

    missing_segments = [sid for sid in claim.segment_ids if sid not in segment_by_id]
    if missing_segments:
        reasons.append(f"unknown segment_ids: {', '.join(missing_segments)}")
        scope_text = full_text
    elif claim.segment_ids:
        scope_text = " ".join(segment_by_id[sid] for sid in claim.segment_ids)
    else:
        scope_text = full_text

    if claim.source_quote not in scope_text:
        reasons.append("source_quote does not appear verbatim in the referenced text")

    src_numbers = extract_number_anchors(claim.source_quote, language)
    standalone_numbers = extract_number_anchors(claim.standalone_claim, language)
    invented_numbers = sorted(standalone_numbers - src_numbers)
    if invented_numbers:
        reasons.append(
            "standalone_claim introduces numbers absent from source_quote: "
            f"{', '.join(invented_numbers)}"
        )

    if has_negation(claim.source_quote, language) != has_negation(
        claim.standalone_claim, language
    ):
        reasons.append("negation differs between source_quote and standalone_claim")

    if has_future_plan(claim.standalone_claim, language) and not has_future_plan(
        claim.source_quote, language
    ):
        reasons.append("standalone_claim adds future-plan framing absent from source_quote")

    if has_uncertainty(claim.source_quote, language) != has_uncertainty(
        claim.standalone_claim, language
    ):
        reasons.append("uncertainty framing differs between source_quote and standalone_claim")

    grounded_entities = _ground_metadata(
        claim.entities, scope_text, claim.standalone_claim, language, numeric=False
    )
    grounded_dates = _ground_metadata(
        claim.dates, claim.source_quote, claim.standalone_claim, language, numeric=True
    )
    grounded_numbers = _ground_metadata(
        claim.numbers, claim.source_quote, claim.standalone_claim, language, numeric=True
    )
    grounded_attribution: str | None = None
    if claim.attribution:
        matched = _ground_metadata(
            [claim.attribution], scope_text, claim.standalone_claim, language, numeric=False
        )
        grounded_attribution = matched[0] if matched else None

    return ClaimGroundingCheck(
        id=claim_id,
        grounded=not reasons,
        reasons=reasons,
        facets=extract_facets(claim.source_quote, language),
        grounded_entities=grounded_entities,
        grounded_dates=grounded_dates,
        grounded_numbers=grounded_numbers,
        grounded_attribution=grounded_attribution,
    )


def verify_query_anchors(
    query: SearchQueryInput,
    *,
    required_anchors: set[str],
) -> QueryAnchorCheck:
    """Verify that a search query preserves required numeric/date anchors."""
    rendered = f"{query.exact_query} {query.context_query}".strip()
    query_anchors = extract_number_anchors(rendered, query.language)
    raw_digits = {
        re.sub(r"[.,]", "", token) for token in re.findall(r"\d[\d.,]*", rendered)
    }
    present = query_anchors | raw_digits
    missing = sorted(anchor for anchor in required_anchors if anchor not in present)
    return QueryAnchorCheck(
        language=query.language,
        passed=not missing,
        missing_anchors=missing,
    )


def analyze_claims(
    text: str,
    *,
    language: LanguageOrAuto = "auto",
    claims: list[ClaimInput] | None = None,
    queries: list[SearchQueryInput] | None = None,
    max_segments: int = 80,
) -> AnalyzeClaimsResult:
    """Segment text, extract facets, and validate optional candidate claims and search queries."""
    lang = resolve_language(text, language)
    segments = segment_article(text, lang)
    segment_by_id = {segment.id: segment.text for segment in segments}
    text_facets = extract_facets(text, lang)

    claim_checks = [
        verify_claim_grounding(
            claim,
            full_text=text,
            segment_by_id=segment_by_id,
            language=lang,
            index=idx + 1,
        )
        for idx, claim in enumerate(claims or [])
    ]

    grounded_claims = [
        claim
        for claim, check in zip(claims or [], claim_checks, strict=True)
        if check.grounded
    ]
    if grounded_claims:
        anchor_source = " ".join(claim.standalone_claim for claim in grounded_claims)
    elif claims:
        anchor_source = " ".join(claim.source_quote for claim in claims)
    else:
        anchor_source = text
    required_anchors = extract_number_anchors(anchor_source, lang)
    query_checks = [
        verify_query_anchors(query, required_anchors=required_anchors)
        for query in (queries or [])
    ]

    truncated = len(segments) > max_segments
    return AnalyzeClaimsResult(
        language=lang,
        segment_count=len(segments),
        segments=segments[:max_segments],
        text_facets=text_facets,
        claim_checks=claim_checks,
        query_checks=query_checks,
        truncated=truncated,
        dropped_fields=["segments"] if truncated else [],
    )


def _ground_metadata(
    values: list[str],
    source_text: str,
    standalone_claim: str,
    language: Language,
    *,
    numeric: bool,
) -> list[str]:
    source_normalized = unicodedata.normalize("NFKC", source_text).casefold()
    standalone_normalized = unicodedata.normalize("NFKC", standalone_claim).casefold()
    source_anchors = extract_number_anchors(source_text, language)
    standalone_anchors = extract_number_anchors(standalone_claim, language)
    kept: list[str] = []
    for value in values:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        anchors = extract_number_anchors(value, language) if numeric else set()
        if anchors:
            ok = anchors.issubset(source_anchors) and anchors.issubset(standalone_anchors)
        else:
            ok = normalized in source_normalized and normalized in standalone_normalized
        if ok:
            kept.append(value)
    return kept
