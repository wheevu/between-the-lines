"""Tests for claim grounding, query-anchor checks, and edition diffing."""

from __future__ import annotations

from btl.claims import analyze_claims
from btl.provenance import canonicalize_url, diff_editions
from btl.types import ClaimInput, EditionDiffCategory, SearchQueryInput


def test_analyze_claims_validates_grounding_and_query_anchors() -> None:
    text = (
        "The ministry announced on April 27, 2026 that 12 provinces joined the program.\n\n"
        "Officials did not publish the final budget."
    )
    good_claim = ClaimInput(
        id="c-good",
        source_quote=(
            "The ministry announced on April 27, 2026 that 12 provinces joined the program."
        ),
        standalone_claim="12 provinces joined the program on April 27, 2026.",
        segment_ids=["p1s1"],
        numbers=["12"],
        dates=["April 27, 2026"],
    )
    bad_claim = ClaimInput(
        id="c-bad",
        source_quote="Officials did not publish the final budget.",
        standalone_claim="Officials published 500 billion in final budget.",
        segment_ids=["p2s1"],
    )
    queries = [
        SearchQueryInput(
            language="en",
            exact_query="ministry 12 provinces April 27 2026",
            context_query="ministry program",
        ),
        SearchQueryInput(
            language="vi",
            exact_query="bộ 12 tỉnh 2026",  # misses month 4 and day 27
            context_query="chương trình mới",
        ),
    ]
    res = analyze_claims(text, language="en", claims=[good_claim, bad_claim], queries=queries)
    assert res.segment_count == 2
    assert res.claim_checks[0].grounded is True
    assert res.claim_checks[1].grounded is False
    assert len(res.claim_checks[1].reasons) >= 2
    assert res.query_checks[0].passed is True
    assert res.query_checks[1].passed is False
    assert "27" in res.query_checks[1].missing_anchors


def test_diff_editions_tracks_numbers_dates_negation_modality_and_legal_state() -> None:
    before = (
        "According to reports, police are investigating a 10 billion won allegation "
        "in March 2025."
    )
    after = "The court ruled on April 10, 2026 that the firm did not owe 15 billion won."
    diff = diff_editions(before, after, before_language="en", after_language="en")
    assert diff.changed is True
    assert diff.before_sha256 != diff.after_sha256
    categories = {change.category for change in diff.changes}
    assert EditionDiffCategory.NUMBER in categories
    assert EditionDiffCategory.DATE in categories
    assert EditionDiffCategory.NEGATION in categories
    assert EditionDiffCategory.LEGAL_STATE in categories


def test_canonicalize_url_normalizes_tracking_www_and_ports() -> None:
    a = canonicalize_url("HTTPS://WWW.Example.com:443/news/?utm_source=x&id=2&fbclid=y")
    b = canonicalize_url("https://example.com/news?id=2")
    assert a == b
    assert a == "https://example.com/news?id=2"
