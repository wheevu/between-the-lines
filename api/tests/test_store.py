import sqlite3
from pathlib import Path

from app.models import (
    AnalysisResult,
    ClaimCandidate,
    ClaimType,
    FactCheckFeedbackCreate,
    FactCheckFeedbackTarget,
    FactCheckResult,
    FactCheckStatus,
    FeedbackCreate,
    FeedbackVerdict,
    Language,
)
from app.store import Store


def test_store_round_trips_job_and_feedback(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    job = store.create_analysis()

    loaded = store.get_analysis(job.id)
    feedback = store.add_feedback(
        job.id,
        FeedbackCreate(flag_id="flag-1", verdict=FeedbackVerdict.HELPFUL),
    )

    assert loaded == job
    assert feedback.analysis_id == job.id
    assert feedback.flag_id == "flag-1"


def test_store_round_trips_cached_analysis(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    result = AnalysisResult(source_language=Language.ENGLISH, segments=[])

    store.cache_result("same-input", result)

    assert store.get_cached_result("same-input") == result


def test_new_feedback_replaces_the_previous_judgment(tmp_path: Path) -> None:
    path = tmp_path / "test.sqlite3"
    store = Store(path)
    store.initialize()
    job = store.create_analysis()

    first = store.add_feedback(
        job.id,
        FeedbackCreate(flag_id="flag-1", verdict=FeedbackVerdict.HELPFUL),
    )
    updated = store.add_feedback(
        job.id,
        FeedbackCreate(
            flag_id="flag-1",
            verdict=FeedbackVerdict.INCORRECT,
            correction="The warning overstates the difference.",
        ),
    )
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

    assert updated.id == first.id
    assert updated.verdict is FeedbackVerdict.INCORRECT
    assert count == 1


def test_store_round_trips_one_fact_check_per_analysis(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    analysis = store.create_analysis()
    created, was_created = store.create_or_get_fact_check(analysis.id)
    same, was_created_again = store.create_or_get_fact_check(analysis.id)
    candidate = ClaimCandidate(
        id="claim-1",
        source_quote="The agency reported 20 cases.",
        segment_ids=["p1s1"],
        standalone_claim="The agency reported 20 cases.",
        claim_type=ClaimType.ATTRIBUTED,
        numbers=["20"],
        reason="A specific attributed number.",
    )

    store.update_fact_check(
        created.id,
        status=FactCheckStatus.AWAITING_SELECTION,
        stage="Choose claims to check",
        progress=100,
        candidates=[candidate],
        selected_candidate_ids=[candidate.id],
        result=FactCheckResult(claims=[], checked_at="2026-07-24T00:00:00Z"),
    )
    loaded = store.get_fact_check(created.id)

    assert was_created
    assert not was_created_again
    assert same.id == created.id
    assert loaded is not None
    assert loaded.candidates == [candidate]
    assert loaded.selected_candidate_ids == ["claim-1"]
    assert loaded.result is not None
    assert loaded.result.checked_at == "2026-07-24T00:00:00Z"


def test_fact_check_feedback_updates_one_target_in_place(tmp_path: Path) -> None:
    path = tmp_path / "test.sqlite3"
    store = Store(path)
    store.initialize()
    analysis = store.create_analysis()
    fact_check, _ = store.create_or_get_fact_check(analysis.id)

    first = store.add_fact_check_feedback(
        fact_check.id,
        FactCheckFeedbackCreate(
            target_type=FactCheckFeedbackTarget.EVIDENCE,
            target_id="evidence-1",
            verdict=FeedbackVerdict.HELPFUL,
        ),
    )
    updated = store.add_fact_check_feedback(
        fact_check.id,
        FactCheckFeedbackCreate(
            target_type=FactCheckFeedbackTarget.EVIDENCE,
            target_id="evidence-1",
            verdict=FeedbackVerdict.INCORRECT,
            correction="This excerpt concerns a different date.",
            better_source_url="https://primary.example/record",
        ),
    )
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM fact_check_feedback").fetchone()[0]

    assert updated.id == first.id
    assert updated.verdict is FeedbackVerdict.INCORRECT
    assert str(updated.better_source_url) == "https://primary.example/record"
    assert count == 1
