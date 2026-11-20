"""Tests for SSRF guards and bounded batch URL extraction."""

from __future__ import annotations

import pytest

from btl.extractor import ArticleExtractionError, _validate_public_url, fetch_batch
from btl.types import ExtractedDocument


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://127.0.0.1:8000/secret",
        "http://localhost/admin",
        "http://10.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/file",
        "https://user:pass@example.com/article",
    ],
)
def test_validate_public_url_blocks_private_loopback_and_credentials(bad_url: str) -> None:
    with pytest.raises(ArticleExtractionError):
        _validate_public_url(bad_url)


def test_fetch_batch_excludes_self_citations_duplicates_and_caps_publishers() -> None:
    def fake_extractor(url: str) -> ExtractedDocument:
        return ExtractedDocument(
            url=url,
            canonical_url=url,
            title=f"Title for {url}",
            published_at_unverified="2026-10-01",
            publisher="news.example",
            text=f"Unique body for {url} with sufficient prose content to inspect clearly.",
        )

    urls = [
        "https://news.example/source-article",
        "https://news.example/p1?utm_source=feed",
        "https://news.example/p1",
        "https://news.example/p2",
        "https://news.example/p3",
        "https://news.example/p4",
        "http://127.0.0.1/private",
    ]
    docs, failures = fetch_batch(
        urls,
        input_url="https://news.example/source-article",
        limit=12,
        max_per_publisher=2,
        extractor=fake_extractor,
    )
    assert len(docs) == 2
    assert {doc.canonical_url for doc in docs} == {
        "https://news.example/p1",
        "https://news.example/p2",
    }
    assert any("cite itself" in f.reason for f in failures)
