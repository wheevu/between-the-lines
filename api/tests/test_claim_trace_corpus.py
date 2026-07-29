import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

MANIFEST = Path(__file__).parents[1] / "evaluation" / "claim-trace-corpus.json"
ROBUSTNESS_MANIFEST = (
    Path(__file__).parents[1] / "evaluation" / "claim-trace-robustness-corpus.json"
)
LANGUAGES = {"en", "ko", "vi"}
TOPICS = {
    "culture_sports",
    "education_society",
    "health",
    "public_policy",
    "science_climate",
    "technology_economy",
}


def _corpus() -> dict:
    return json.loads(MANIFEST.read_text())


def test_claim_trace_corpus_has_balanced_event_and_language_coverage() -> None:
    data = _corpus()
    events = data["events"]
    articles = [article for event in events for article in event["articles"]]
    trace_cases = [case for event in events for case in event["trace_cases"]]

    assert len(events) == data["design"]["events"] == 12
    assert len(articles) == data["design"]["articles"] == 36
    assert len(trace_cases) == data["design"]["trace_cases"] == 24
    assert Counter(event["topic"] for event in events) == {topic: 2 for topic in TOPICS}
    assert Counter(case["seed_language"] for case in trace_cases) == {
        "en": 8,
        "ko": 8,
        "vi": 8,
    }

    for event in events:
        assert len(event["articles"]) == 3
        assert {article["source_language"] for article in event["articles"]} == LANGUAGES
        assert len(event["trace_cases"]) == 2


def test_claim_trace_corpus_is_unique_and_within_frozen_window() -> None:
    data = _corpus()
    events = data["events"]
    articles = [article for event in events for article in event["articles"]]
    trace_cases = [case for event in events for case in event["trace_cases"]]
    start = date.fromisoformat(data["window"]["start"])
    end = date.fromisoformat(data["window"]["end"])

    assert len({event["id"] for event in events}) == len(events)
    assert len({article["id"] for article in articles}) == len(articles)
    assert len({article["url"] for article in articles}) == len(articles)
    assert len({case["id"] for case in trace_cases}) == len(trace_cases)

    for article in articles:
        published = date.fromisoformat(article["published"])
        parsed_url = urlparse(article["url"])

        assert start <= published <= end
        assert parsed_url.scheme == "https"
        assert parsed_url.netloc
        assert article["title"].strip()
        assert article["publisher"].strip()


def test_claim_trace_corpus_covers_precision_and_objectivity_edges() -> None:
    data = _corpus()
    events = data["events"]
    all_edges = {
        edge
        for event in events
        for edge in (
            event["edge_tags"]
            + [tag for article in event["articles"] for tag in article["edge_tags"]]
        )
    }

    assert Counter(event["profile"] for event in events) == {
        "challenging": 6,
        "clean": 6,
    }
    assert {
        "attribution",
        "forecast_modality",
        "legal_state",
        "local_framing",
        "numeric_precision",
        "scope",
        "source_lineage",
        "syndication",
        "temporal_update",
    } <= all_edges


def test_robustness_corpus_is_balanced_but_not_labeled_as_gold() -> None:
    data = json.loads(ROBUSTNESS_MANIFEST.read_text())
    articles = [article for event in data["events"] for article in event["articles"]]

    assert len(data["events"]) == 12
    assert len(articles) == data["summary"]["articles"] == 120
    assert Counter(article["source_language"] for article in articles) == {
        "en": 40,
        "ko": 40,
        "vi": 40,
    }
    assert Counter(event["topic"] for event in data["events"]) == {topic: 2 for topic in TOPICS}
    assert len({article["id"] for article in articles}) == len(articles)
    assert len({article["url"] for article in articles}) == len(articles)
    assert "not a factual gold set" in data["purpose"]

    for event in data["events"]:
        assert len(event["articles"]) == 10
        assert len({urlparse(article["url"]).hostname for article in event["articles"]}) == 10
        assert set(
            Counter(article["source_language"] for article in event["articles"]).values()
        ) <= {3, 4}
        for article in event["articles"]:
            assert urlparse(article["url"]).scheme in {"http", "https"}
            assert article["title"].strip()
            assert article["publisher"].strip()
