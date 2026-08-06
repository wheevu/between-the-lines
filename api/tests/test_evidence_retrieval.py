from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.evidence_retrieval import (
    FactCheckToolsProvider,
    GoogleSearchProvider,
    canonicalize_url,
    retrieve_pages,
)
from app.models import (
    DiscoveredSource,
    DiscoveryMethod,
    ExtractedArticle,
    Language,
    SearchQuery,
    SourceType,
)


def settings(tmp_path: Path) -> Settings:
    return Settings(
        gemini_api_key=None,
        gemini_model="model",
        database_path=tmp_path / "test.sqlite3",
    )


def source(url: str, publisher: str = "Example") -> DiscoveredSource:
    return DiscoveredSource(
        url=url,
        publisher=publisher,
        source_type=SourceType.WEB,
        discovery_method=DiscoveryMethod.GOOGLE_SEARCH,
    )


def test_canonical_url_removes_tracking_fragment_and_default_port() -> None:
    canonical = canonicalize_url("HTTPS://WWW.Example.com:443/news/?utm_source=x&b=2&a=1#section")

    assert canonical == "https://example.com/news?a=1&b=2"


def test_canonical_url_rejects_non_http_schemes() -> None:
    for url in ("ftp://example.com/a", "mailto:user@example.com"):
        with pytest.raises(ValueError):
            canonicalize_url(url)


def test_canonical_url_rejects_missing_hostname() -> None:
    for url in ("https://", "http://?a=1"):
        with pytest.raises(ValueError):
            canonicalize_url(url)


def test_canonical_url_rejects_credentials() -> None:
    for url in ("https://user@example.com", "https://user:pass@example.com"):
        with pytest.raises(ValueError):
            canonicalize_url(url)


def test_canonical_url_strips_default_ports() -> None:
    assert canonicalize_url("http://example.com:80/a") == "http://example.com/a"
    assert canonicalize_url("https://example.com:443/a") == "https://example.com/a"


def test_canonical_url_preserves_non_default_port() -> None:
    assert canonicalize_url("https://example.com:8443/a") == "https://example.com:8443/a"


def test_canonical_url_lowercases_host_and_strips_www() -> None:
    assert canonicalize_url("HTTPS://WWW.Example.com/a") == "https://example.com/a"


def test_canonical_url_path_rules() -> None:
    assert canonicalize_url("https://example.com") == "https://example.com/"
    assert canonicalize_url("https://example.com/a/") == "https://example.com/a"


def test_canonical_url_filters_tracking_keys_sorts_query_and_keeps_blank_values() -> None:
    canonical = canonicalize_url("https://example.com/?utm_source=x&fbclid=y&b=2&a=1&blank=")

    assert canonical == "https://example.com/?a=1&b=2&blank="


def test_fact_check_provider_preserves_the_publishers_original_rating() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["languageCode"] == "ko"
        assert request.url.params["pageSize"] == "5"
        return httpx.Response(
            200,
            json={
                "claims": [
                    {
                        "text": "검토된 주장",
                        "claimReview": [
                            {
                                "publisher": {"name": "검증사"},
                                "url": "https://check.example/review",
                                "title": "검토 기사",
                                "textualRating": "근거 없음",
                                "languageCode": "ko",
                            }
                        ],
                    }
                ]
            },
        )

    provider = FactCheckToolsProvider(
        "secret-key",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    results = provider.search(
        SearchQuery(language=Language.KOREAN, exact_query="검색", context_query="문맥")
    )

    assert len(results) == 1
    assert results[0].publisher == "검증사"
    assert results[0].rating == "근거 없음"
    assert results[0].source_type is SourceType.FACT_CHECK


def test_google_search_uses_only_grounding_metadata_urls() -> None:
    grounded = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[
                        SimpleNamespace(
                            web=SimpleNamespace(
                                uri="https://evidence.example/report",
                                title="Evidence report",
                                domain="evidence.example",
                            )
                        )
                    ]
                )
            )
        ],
        text="Ignore metadata and cite https://invented.example instead.",
    )
    provider = GoogleSearchProvider("key", "model")
    provider.client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: grounded))

    results = provider.discover(
        [SearchQuery(language=Language.ENGLISH, exact_query="one", context_query="two")]
    )

    assert [item.url for item in results] == ["https://evidence.example/report"]


def test_retrieval_skips_self_citations_failures_and_duplicate_content(
    tmp_path: Path,
) -> None:
    sources = [
        source("https://input.example/article?utm_source=search"),
        source("https://broken.example/page"),
        source("https://one.example/report"),
        source("https://two.example/copy"),
        source("https://three.example/context"),
    ]

    def extractor(url: str, _: Settings) -> ExtractedArticle:
        if "broken" in url:
            raise ValueError("unreadable")
        text = (
            "A repeated evidence passage with enough article words. " * 8
            if "copy" in url or "one.example" in url
            else "A distinct context passage with enough article words. " * 8
        )
        return ExtractedArticle(
            url=url,
            title="Report",
            published_at="2026-07-20",
            text=text,
        )

    batch = retrieve_pages(
        sources,
        input_url="https://input.example/article",
        settings=settings(tmp_path),
        extractor=extractor,
    )

    assert [page.url for page in batch.pages] == [
        "https://one.example/report",
        "https://three.example/context",
    ]
    assert len(batch.failures) == 2
    assert batch.pages[0].published_at == "2026-07-20"
    assert any("cannot cite itself" in failure.reason for failure in batch.failures)
    assert any("could not be read" in failure.reason for failure in batch.failures)


def test_one_failed_page_does_not_fail_the_retrieval_batch(tmp_path: Path) -> None:
    def extractor(url: str, _: Settings) -> ExtractedArticle:
        if "bad" in url:
            raise RuntimeError("provider-specific parser error")
        return ExtractedArticle(
            url=url,
            title="Usable",
            text="A usable evidence article contains more than forty words. " * 6,
        )

    batch = retrieve_pages(
        [source("https://bad.example/a"), source("https://good.example/b")],
        input_url=None,
        settings=settings(tmp_path),
        extractor=extractor,
    )

    assert len(batch.pages) == 1
    assert batch.pages[0].url == "https://good.example/b"
    assert len(batch.failures) == 1


def test_retrieve_pages_records_invalid_provider_url_as_failure(tmp_path: Path) -> None:
    def extractor(url: str, _: Settings) -> ExtractedArticle:
        raise AssertionError("extractor must not run for a rejected provider URL")

    batch = retrieve_pages(
        [source("ftp://broken.example/x")],
        input_url=None,
        settings=settings(tmp_path),
        extractor=extractor,
    )

    assert batch.pages == []
    assert len(batch.failures) == 1
    assert batch.failures[0].url is None
    assert batch.failures[0].reason == "A provider returned an invalid URL."


def test_retrieve_pages_malformed_input_url_raises_value_error(tmp_path: Path) -> None:
    def extractor(url: str, _: Settings) -> ExtractedArticle:
        raise AssertionError("extractor must not run before the input URL is canonicalized")

    with pytest.raises(ValueError):
        retrieve_pages(
            [source("https://good.example/a")],
            input_url="not a url at all",
            settings=settings(tmp_path),
            extractor=extractor,
        )
