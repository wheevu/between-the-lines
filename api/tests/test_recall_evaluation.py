import json
from hashlib import sha256
from pathlib import Path

from app.config import Settings
from app.evidence_retrieval import RetrievalBatch, RetrievedPage
from app.fact_checker import _evidence_items
from app.models import DiscoveredSource, DiscoveryMethod, SourceType
from app.recall_evaluation import (
    contains_quote,
    run_recall_diagnostics,
    validate_publisher_holdout,
    validate_recall_oracle,
)

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


class FakeLocalModels:
    def similarities(self, left, right):
        del left
        return [0.99 if "exact gold passage" in text else 0.1 for text in right]


def manifest() -> dict:
    return {
        "events": [
            {
                "id": "event",
                "topic": "science",
                "trace_cases": [
                    {
                        "id": "case-en",
                        "seed_language": "en",
                        "seed_claim": "The report contains a gold fact.",
                    }
                ],
                "articles": [
                    {
                        "id": "source-en",
                        "source_language": "en",
                        "publisher": "Source",
                        "title": "Source",
                        "url": "https://source.example/article",
                    },
                    {
                        "id": "comparison-vi",
                        "source_language": "vi",
                        "publisher": "One",
                        "title": "One",
                        "url": "https://one.example/article",
                    },
                    {
                        "id": "comparison-ko",
                        "source_language": "ko",
                        "publisher": "Two",
                        "title": "Two",
                        "url": "https://two.example/article",
                    },
                ],
            }
        ]
    }


def oracle() -> dict:
    return {
        "schema_version": 1,
        "corpus_sha256": "corpus-hash",
        "reviewer_role": "author",
        "cases": [
            {
                "case_id": "case-en",
                "answerability": "answerable",
                "reviewed_article_ids": ["comparison-vi", "comparison-ko"],
                "gold_passages": [
                    {
                        "article_id": "comparison-vi",
                        "quote": "An exact gold passage confirms the report.",
                    }
                ],
                "rationale": "One comparison article contains the claim.",
            }
        ],
    }


def page() -> RetrievedPage:
    text = (
        "Background sentence with ordinary context. " * 30
        + "An exact gold passage confirms the report. "
        + "Closing context sentence. " * 30
    )
    return RetrievedPage(
        source=DiscoveredSource(
            url="https://one.example/article",
            title="One",
            publisher="One",
            source_type=SourceType.WEB,
            discovery_method=DiscoveryMethod.GOOGLE_SEARCH,
        ),
        url="https://one.example/article",
        title="One",
        text=text,
        content_hash=sha256(text.encode()).hexdigest(),
    )


def test_quote_matching_normalizes_unicode_case_and_whitespace() -> None:
    assert contains_quote("Ａ  Report\nCONFIRMS the fact", "a report confirms   the fact")


def test_oracle_requires_both_comparison_articles_and_gold_for_answerable_case() -> None:
    data = oracle()
    data["cases"][0]["reviewed_article_ids"] = ["comparison-vi"]
    data["cases"][0]["gold_passages"] = []

    summary = validate_recall_oracle(data, manifest(), "corpus-hash")

    assert not summary["ready_for_diagnostics"]
    assert summary["case_issues"] == [
        {
            "case_id": "case-en",
            "issues": [
                "An answerable case needs at least one gold passage.",
                "Record both permitted comparison article IDs.",
            ],
        }
    ]


def test_diagnostic_localizes_a_passing_gold_passage_without_storing_article_text(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retrieved_page = page()
    batch = RetrievalBatch(pages=[retrieved_page], failures=[])
    monkeypatch.setattr(
        "app.recall_evaluation.retrieve_pages",
        lambda *args, **kwargs: batch,
    )
    item = next(
        item
        for item in _evidence_items([retrieved_page])
        if contains_quote(item.excerpt, "An exact gold passage confirms the report.")
    )
    baseline = {
        "results": [
            {
                "case_id": "case-en",
                "evidence": [
                    {
                        "id": item.id,
                        "url": "https://one.example/article",
                        "alignment_state": "aligned",
                    }
                ],
            }
        ]
    }

    result = run_recall_diagnostics(
        manifest(),
        oracle(),
        baseline,
        Settings(
            gemini_api_key=None,
            gemini_model="model",
            database_path=tmp_path / "test.sqlite3",
        ),
        FakeLocalModels(),
    )

    assert result["cases"][0]["failure_stage"] == "passed"
    assert result["summary"]["strict_aligned_recall"] == {
        "passed": 1,
        "eligible": 1,
        "rate": 1.0,
    }
    assert retrieved_page.text not in str(result)
    assert "quote" not in result["cases"][0]["gold"][0]


def test_frozen_publisher_holdout_is_balanced_and_uses_only_robustness_articles() -> None:
    core = json.loads((EVALUATION_DIR / "claim-trace-corpus.json").read_text())
    robustness_path = EVALUATION_DIR / "claim-trace-robustness-corpus.json"
    robustness = json.loads(robustness_path.read_text())
    holdout = json.loads((EVALUATION_DIR / "claim-trace-publisher-holdout-v1.json").read_text())

    summary = validate_publisher_holdout(
        holdout,
        robustness,
        core,
        sha256(robustness_path.read_bytes()).hexdigest(),
    )

    assert summary["ready_for_retrieval_diagnostics"]
    assert summary["language_counts"] == {"en": 4, "ko": 4, "vi": 4}
    assert set(summary["topic_counts"].values()) == {2}
