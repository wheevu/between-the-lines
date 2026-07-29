from pathlib import Path

from app.claim_trace_benchmark import run_preflight
from app.config import Settings
from app.models import ExtractedArticle


def _settings() -> Settings:
    return Settings(
        gemini_api_key=None,
        gemini_model="test",
        database_path=Path("test.sqlite3"),
        max_article_words=100,
    )


def _manifest() -> dict:
    return {
        "prepared": "2026-07-24",
        "events": [
            {
                "id": "event",
                "topic": "science_climate",
                "articles": [
                    {
                        "id": "en-ready",
                        "source_language": "en",
                        "published": "2026-06-01",
                        "title": "A useful report",
                        "url": "https://example.com/en",
                    },
                    {
                        "id": "vi-bad-date",
                        "source_language": "vi",
                        "published": "2026-06-02",
                        "title": "Một báo cáo hữu ích",
                        "url": "https://example.com/vi",
                    },
                    {
                        "id": "ko-too-long",
                        "source_language": "ko",
                        "published": "2026-06-03",
                        "title": "유용한 보고서",
                        "url": "https://example.com/ko",
                    },
                ],
            }
        ],
    }


def test_preflight_reports_readiness_without_storing_article_text() -> None:
    texts = {
        "https://example.com/en": ("The report contains useful evidence. " * 10, "2026-06-01"),
        "https://example.com/vi": (
            "Báo cáo này chứa bằng chứng hữu ích. " * 10,
            "2026-07-24",
        ),
        "https://example.com/ko": ("이 보고서는 유용한 근거를 담고 있다. " * 40, None),
    }

    def extractor(url: str, settings: Settings) -> ExtractedArticle:
        del settings
        text, published = texts[url]
        return ExtractedArticle(
            url=url,
            title={
                "https://example.com/en": "A useful report",
                "https://example.com/vi": "Một báo cáo hữu ích",
                "https://example.com/ko": "유용한 보고서",
            }[url],
            published_at=published,
            text=text,
        )

    report = run_preflight(
        _manifest(),
        _settings(),
        workers=2,
        extractor=extractor,
    )

    assert report["stores_article_text"] is False
    assert [result["id"] for result in report["results"]] == [
        "en-ready",
        "vi-bad-date",
        "ko-too-long",
    ]
    assert all("text" not in result for result in report["results"])
    assert report["summary"]["extracted"] == 3
    assert report["summary"]["ready"] == 2
    assert report["summary"]["date_metadata"] == {
        "exact": 1,
        "missing": 1,
        "mismatch": 1,
    }
    assert report["summary"]["over_word_limit"] == ["ko-too-long"]
    assert report["summary"]["language_mismatches"] == []


def test_preflight_records_extraction_failure_without_aborting_other_articles() -> None:
    def extractor(url: str, settings: Settings) -> ExtractedArticle:
        del settings
        if url.endswith("/vi"):
            raise ValueError("blocked")
        language = "ko" if url.endswith("/ko") else "en"
        text = (
            "이 보고서는 유용한 근거를 담고 있다."
            if language == "ko"
            else "The report contains useful evidence."
        )
        return ExtractedArticle(
            url=url,
            title="Title",
            published_at=None,
            text=text,
        )

    report = run_preflight(
        _manifest(),
        _settings(),
        workers=3,
        extractor=extractor,
    )

    assert report["summary"]["extracted"] == 2
    assert report["summary"]["failed"] == 1
    assert report["summary"]["failure_ids"] == ["vi-bad-date"]
    failed = report["results"][1]
    assert failed["error_type"] == "ValueError"
    assert failed["error"] == "blocked"
