import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from hashlib import sha256
from statistics import median
from time import perf_counter

from app.article import extract_article
from app.config import Settings
from app.language_detection import detect_language
from app.models import ExtractedArticle

Extractor = Callable[[str, Settings], ExtractedArticle]
NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def run_preflight(
    manifest: dict,
    settings: Settings,
    *,
    workers: int = 6,
    extractor: Extractor = extract_article,
) -> dict:
    if workers < 1:
        raise ValueError("workers must be positive.")
    indexed_articles = [
        (index, event["id"], event["topic"], article)
        for index, (event, article) in enumerate(
            (event, article) for event in manifest["events"] for article in event["articles"]
        )
    ]
    results: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _probe_article,
                event_id,
                topic,
                article,
                settings,
                extractor,
            ): index
            for index, event_id, topic, article in indexed_articles
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    ordered = [results[index] for index, *_ in indexed_articles]
    return {
        "schema_version": 1,
        "corpus_prepared": manifest["prepared"],
        "corpus_sha256": _manifest_digest(manifest),
        "stores_article_text": False,
        "results": ordered,
        "summary": summarize_preflight(ordered),
    }


def summarize_preflight(results: list[dict]) -> dict:
    ready = [result for result in results if result.get("ready")]
    extracted = [result for result in results if result.get("extracted")]
    failed = [result for result in results if not result.get("extracted")]
    date_counts = Counter(result["date_status"] for result in extracted if "date_status" in result)

    def coverage(field: str) -> dict[str, dict[str, int]]:
        values = sorted({result[field] for result in results})
        return {
            value: {
                "total": sum(result[field] == value for result in results),
                "ready": sum(
                    result[field] == value and bool(result.get("ready")) for result in results
                ),
            }
            for value in values
        }

    return {
        "total": len(results),
        "extracted": len(extracted),
        "ready": len(ready),
        "failed": len(failed),
        "ready_rate": round(len(ready) / len(results), 4) if results else 0,
        "median_seconds": round(median(result["seconds"] for result in results), 3)
        if results
        else 0,
        "date_metadata": {
            "exact": date_counts["exact"],
            "missing": date_counts["missing"],
            "mismatch": date_counts["mismatch"],
        },
        "title_matches": sum(bool(result.get("title_match")) for result in extracted),
        "language_mismatches": [
            result["id"] for result in extracted if not result.get("language_match", False)
        ],
        "over_word_limit": [
            result["id"] for result in extracted if not result.get("within_word_limit", False)
        ],
        "failure_ids": [result["id"] for result in failed],
        "by_language": coverage("source_language"),
        "by_topic": coverage("topic"),
    }


def _probe_article(
    event_id: str,
    topic: str,
    article: dict,
    settings: Settings,
    extractor: Extractor,
) -> dict:
    started = perf_counter()
    base = {
        "id": article["id"],
        "event_id": event_id,
        "topic": topic,
        "source_language": article["source_language"],
        "url": article["url"],
    }
    try:
        extracted = extractor(article["url"], settings)
    except Exception as error:
        return {
            **base,
            "extracted": False,
            "ready": False,
            "seconds": round(perf_counter() - started, 3),
            "error_type": type(error).__name__,
            "error": str(error),
        }

    word_count = len(extracted.text.split())
    detected_language = detect_language(extracted.text).value
    extracted_date = extracted.published_at
    expected_date = article["published"]
    date_status = (
        "missing"
        if not extracted_date
        else "exact"
        if extracted_date == expected_date
        else "mismatch"
    )
    title_similarity = _title_similarity(article["title"], extracted.title or "")
    language_match = detected_language == article["source_language"]
    within_word_limit = word_count <= settings.max_article_words
    ready = language_match and within_word_limit
    return {
        **base,
        "extracted": True,
        "ready": ready,
        "seconds": round(perf_counter() - started, 3),
        "word_count": word_count,
        "within_word_limit": within_word_limit,
        "detected_language": detected_language,
        "language_match": language_match,
        "expected_title": article["title"],
        "extracted_title": extracted.title,
        "title_similarity": title_similarity,
        "title_match": title_similarity >= 0.8,
        "expected_date": expected_date,
        "extracted_date": extracted_date,
        "date_status": date_status,
        "resolved_url": extracted.url,
        "content_sha256": sha256(extracted.text.encode()).hexdigest(),
    }


def _title_similarity(expected: str, actual: str) -> float:
    def normalize(value: str) -> str:
        return NON_WORD.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()

    expected_normalized = normalize(expected)
    actual_normalized = normalize(actual)
    if not expected_normalized or not actual_normalized:
        return 0
    if expected_normalized in actual_normalized or actual_normalized in expected_normalized:
        return 1
    return round(
        SequenceMatcher(None, expected_normalized, actual_normalized).ratio(),
        4,
    )


def _manifest_digest(manifest: dict) -> str:
    import json

    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode()).hexdigest()
