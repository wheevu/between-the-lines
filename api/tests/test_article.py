from pathlib import Path

import httpx
import pytest

import app.article as article
from app.article import ArticleExtractionError, _clean_article_text, extract_article
from app.config import Settings


def test_http_errors_become_safe_extraction_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    def client(*args, **kwargs):
        del args, kwargs
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(article.httpx, "Client", client)
    monkeypatch.setattr(article, "_validate_public_url", lambda _: None)
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    with pytest.raises(ArticleExtractionError, match="HTTP 404"):
        extract_article("https://example.com/story", settings)


def test_article_bytes_use_document_encoding_instead_of_incorrect_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_client = httpx.Client
    sentence = "뉴진스는 네 명의 멤버가 함께한 새로운 사진과 영상을 공개했습니다."
    html = (
        "<html><head><meta charset='euc-kr'>"
        "<title>뉴진스 복귀 소식</title></head><body><article>"
        + " ".join(sentence for _ in range(12))
        + "</article></body></html>"
    ).encode("euc-kr")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=html,
            headers={"content-type": "text/html; charset=utf-8"},
            request=request,
        )

    def client(*args, **kwargs):
        del args, kwargs
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(article.httpx, "Client", client)
    monkeypatch.setattr(article, "_validate_public_url", lambda _: None)
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    result = extract_article("https://example.com/story", settings)

    assert result.title == "뉴진스 복귀 소식"
    assert "뉴진스는 네 명의 멤버" in result.text
    assert "\ufffd" not in result.text


def test_corrupt_extracted_text_requests_a_paste_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_client = httpx.Client
    corrupt_text = " ".join(["���� broken article text with enough words"] * 12)
    html = f"<html><body><article>{corrupt_text}</article></body></html>".encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=html,
            headers={"content-type": "text/html"},
            request=request,
        )

    def client(*args, **kwargs):
        del args, kwargs
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(article.httpx, "Client", client)
    monkeypatch.setattr(article, "_validate_public_url", lambda _: None)
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    with pytest.raises(ArticleExtractionError, match="encoding couldn't be read"):
        extract_article("https://example.com/story", settings)


def test_malformed_optional_metadata_does_not_discard_readable_article(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_client = httpx.Client
    paragraph = "This readable report contains enough useful words for extraction. " * 10
    html = (
        f"<html><head><title>Readable report</title></head>"
        f"<body><article>{paragraph}</article></body></html>"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=html,
            headers={"content-type": "text/html"},
            request=request,
        )

    def client(*args, **kwargs):
        del args, kwargs
        return real_client(transport=httpx.MockTransport(handler))

    def malformed_metadata(*args, **kwargs):
        del args, kwargs
        raise ValueError("invalid publisher timezone")

    monkeypatch.setattr(article.httpx, "Client", client)
    monkeypatch.setattr(article, "_validate_public_url", lambda _: None)
    monkeypatch.setattr(article.trafilatura, "extract_metadata", malformed_metadata)
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    result = extract_article("https://example.com/story", settings)

    assert result.title == "Readable report"
    assert result.published_at is None
    assert "readable report contains" in result.text.lower()


def test_metadata_only_keeps_url_and_title_when_text_cannot_extract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_client = httpx.Client
    html = (
        b"<html><head><title>Unyielding story title</title></head>"
        b"<body><article>short</article></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=html,
            headers={"content-type": "text/html"},
            request=request,
        )

    def client(*args, **kwargs):
        del args, kwargs
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(article.httpx, "Client", client)
    monkeypatch.setattr(article, "_validate_public_url", lambda _: None)
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    url, title = article.extract_metadata("https://example.com/story", settings)

    assert url == "https://example.com/story"
    assert title == "Unyielding story title"


def test_metadata_only_tolerates_an_unreadable_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    def client(*args, **kwargs):
        del args, kwargs
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(article.httpx, "Client", client)
    monkeypatch.setattr(article, "_validate_public_url", lambda _: None)
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    url, title = article.extract_metadata("https://example.com/story", settings)

    assert url is None
    assert title is None


def test_wire_footer_and_related_headlines_are_removed() -> None:
    text = """(ATTN: UPDATES headline)
SEOUL -- Main article paragraph.
Second article paragraph.
reporter@yna.co.kr
(END)
-
Unrelated headline
"""

    assert _clean_article_text(text) == (
        "SEOUL -- Main article paragraph.\nSecond article paragraph."
    )


def test_url_credentials_are_rejected(tmp_path: Path) -> None:
    settings = Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=tmp_path / "test.sqlite3",
    )

    with pytest.raises(ArticleExtractionError, match="credentials"):
        extract_article("https://user:password@example.com/article", settings)
