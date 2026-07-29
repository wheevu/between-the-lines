from pathlib import Path

import app.fact_checker as fact_checker_module
from app.config import Settings
from app.evidence_retrieval import (
    EvidenceDiscoveryError,
    RetrievalBatch,
    RetrievedPage,
)
from app.fact_checker import (
    FactChecker,
    _claim_progress,
    _detect_language,
    _evidence_items,
)
from app.models import (
    AnalysisResult,
    AnalysisStatus,
    ClaimCandidate,
    ClaimType,
    DiscoveredSource,
    DiscoveryMethod,
    EvidenceStance,
    FactCheckStatus,
    Language,
    SearchQuery,
    SegmentResult,
    SourceType,
)
from app.store import Store


def settings(tmp_path: Path) -> Settings:
    return Settings(
        gemini_api_key="key",
        gemini_model="model",
        database_path=tmp_path / "test.sqlite3",
    )


def claim() -> ClaimCandidate:
    return ClaimCandidate(
        id="claim-1",
        source_quote="The agency reported 24 buses.",
        segment_ids=["p1s1"],
        standalone_claim="The agency reported 24 buses.",
        claim_type=ClaimType.FACT,
        numbers=["24"],
        reason="A checkable number.",
    )


def query(language: Language) -> SearchQuery:
    return SearchQuery(
        language=language,
        exact_query=f"agency 24 {language.value}",
        context_query=f"agency buses 24 {language.value}",
    )


def discovered(url: str, publisher: str) -> DiscoveredSource:
    return DiscoveredSource(
        url=url,
        publisher=publisher,
        language=Language.ENGLISH,
        source_type=SourceType.WEB,
        discovery_method=DiscoveryMethod.GOOGLE_SEARCH,
    )


class FakeQueryGenerator:
    def generate(self, _claim):
        return [query(language) for language in Language]


class EmptyFactCheckProvider:
    def search(self, _query):
        return []


class FakeSearchProvider:
    def discover(self, _queries):
        return [
            discovered("https://one.example/report", "One"),
            discovered("https://two.example/report", "Two"),
        ]


class FailedSearchProvider:
    def discover(self, _queries):
        raise EvidenceDiscoveryError("Grounding quota exhausted.")


class FakeLocalModels:
    def similarities(self, left, right):
        del left
        return [0.9 - index * 0.01 for index, _ in enumerate(right)]


class SupportingClassifier:
    def classify(self, _claim, evidence):
        return [
            item.model_copy(
                update={
                    "stance": EvidenceStance.SUPPORTS,
                    "stance_reason": "The excerpt reports the same figure.",
                    "direct": False,
                }
            )
            for item in evidence
        ]


def setup_job(tmp_path: Path) -> tuple[Store, str]:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    analysis = store.create_analysis()
    store.update_analysis(
        analysis.id,
        status=AnalysisStatus.COMPLETE,
        stage="Ready",
        progress=100,
        result=AnalysisResult(
            source_language=Language.ENGLISH,
            source_url="https://input.example/article",
            segments=[
                SegmentResult(
                    id="p1s1",
                    paragraph_index=0,
                    sentence_index=0,
                    source_text=claim().source_quote,
                    translations=[],
                )
            ],
        ),
    )
    job, _ = store.create_or_get_fact_check(analysis.id)
    store.update_fact_check(
        job.id,
        status=FactCheckStatus.RETRIEVING,
        stage="Starting",
        progress=10,
        candidates=[claim()],
        selected_candidate_ids=["claim-1"],
    )
    return store, job.id


def test_worker_persists_ranked_supported_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store, job_id = setup_job(tmp_path)
    page_texts = [
        "The agency report states that 24 buses entered the trial. " * 14,
        "A separate outlet confirms that the trial includes 24 buses. " * 14,
    ]
    pages = [
        RetrievedPage(
            source=discovered(f"https://{index}.example/report", f"Publisher {index}"),
            url=f"https://{index}.example/report",
            title="Report",
            text=text,
            content_hash=f"page-{index}",
        )
        for index, text in enumerate(page_texts)
    ]
    monkeypatch.setattr(
        fact_checker_module,
        "retrieve_pages",
        lambda *args, **kwargs: RetrievalBatch(pages=pages, failures=[]),
    )
    worker = FactChecker(
        settings=settings(tmp_path),
        store=store,
        query_generator=FakeQueryGenerator(),
        fact_check_provider=EmptyFactCheckProvider(),
        search_provider=FakeSearchProvider(),
        local_models=FakeLocalModels(),
        classifier=SupportingClassifier(),
    )

    worker.run(job_id)
    completed = store.get_fact_check(job_id)

    assert completed is not None
    assert completed.status is FactCheckStatus.COMPLETE
    assert completed.result is not None
    result = completed.result.claims[0]
    assert result.assessment.status.value == "supported"
    assert len(result.queries) == 3
    assert len(result.evidence) == 2
    assert result.trace is not None
    assert result.trace.evidence_state.value == "corroborated"
    assert result.trace.independent_lineages == 2


def test_provider_outage_becomes_an_insufficient_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store, job_id = setup_job(tmp_path)
    monkeypatch.setattr(
        fact_checker_module,
        "retrieve_pages",
        lambda *args, **kwargs: RetrievalBatch(pages=[], failures=[]),
    )
    worker = FactChecker(
        settings=settings(tmp_path),
        store=store,
        query_generator=FakeQueryGenerator(),
        fact_check_provider=EmptyFactCheckProvider(),
        search_provider=FailedSearchProvider(),
        local_models=FakeLocalModels(),
        classifier=SupportingClassifier(),
    )

    worker.run(job_id)
    completed = store.get_fact_check(job_id)

    assert completed is not None and completed.result is not None
    claim_result = completed.result.claims[0]
    assert claim_result.assessment.status.value == "insufficient"
    assert claim_result.retrieval_failures[0].reason == "Grounding quota exhausted."
    assert any("unavailable" in item for item in claim_result.assessment.limitations)


def test_language_detection_handles_all_three_scripts() -> None:
    assert _detect_language("The report contains English text.") is Language.ENGLISH
    assert _detect_language("Báo cáo này có tiếng Việt.") is Language.VIETNAMESE
    assert _detect_language("이 보고서는 한국어로 작성됐다.") is Language.KOREAN
    assert _detect_language("The report quoted Université de Montréal.") is Language.ENGLISH
    assert _detect_language("Argentina midfielder Enzo Fernández was booked.") is Language.ENGLISH


def test_near_duplicate_passages_share_one_cluster() -> None:
    base = "The agency said the program may begin in October after a safety review. "
    pages = [
        RetrievedPage(
            source=discovered("https://one.example/a", "One"),
            url="https://one.example/a",
            title="One",
            text=base * 15,
            content_hash="one",
        ),
        RetrievedPage(
            source=discovered("https://two.example/b", "Two"),
            url="https://two.example/b",
            title="Two",
            text=(base * 14) + "A small wording change appears here.",
            content_hash="two",
        ),
    ]

    items = _evidence_items(pages)

    assert len(items) == 2
    assert items[0].cluster_id == items[1].cluster_id


def test_multi_claim_progress_never_moves_backward() -> None:
    values = [
        _claim_progress(number, 3, fraction)
        for number in range(1, 4)
        for fraction in (0, 0.55, 0.8)
    ]

    assert values == sorted(values)
    assert values[0] == 15
    assert values[-1] < 100
