import csv
from io import StringIO
from pathlib import Path

from app.feedback_export import (
    OVERALL_FEEDBACK_PREFIX,
    write_fact_check_feedback,
    write_feedback,
)
from app.models import (
    AnalysisResult,
    AnalysisStatus,
    ClaimAssessment,
    ClaimCandidate,
    ClaimCheckResult,
    ClaimEvidenceStatus,
    ClaimType,
    EvidenceItem,
    EvidenceSourceKind,
    FactCheckFeedbackCreate,
    FactCheckFeedbackTarget,
    FactCheckResult,
    FactCheckStatus,
    FeedbackCreate,
    FeedbackVerdict,
    Language,
    ReviewerRole,
)
from app.store import Store


def test_passage_review_is_exported_with_the_omission_note(tmp_path: Path) -> None:
    path = tmp_path / "test.sqlite3"
    store = Store(path)
    store.initialize()
    job = store.create_analysis()
    store.update_analysis(
        job.id,
        status=AnalysisStatus.COMPLETE,
        stage="Ready to review",
        progress=100,
        result=AnalysisResult(source_language=Language.KOREAN, segments=[]),
    )
    store.add_feedback(
        job.id,
        FeedbackCreate(
            flag_id=f"{OVERALL_FEEDBACK_PREFIX}vi",
            verdict=FeedbackVerdict.INCORRECT,
            correction="The Vietnamese translation lost the uncertainty.",
            reviewer_role=ReviewerRole.AUTHOR,
        ),
    )
    output = StringIO()

    write_feedback(path, output)
    rows = list(csv.DictReader(StringIO(output.getvalue())))

    assert len(rows) == 1
    assert rows[0]["scope"] == "passage"
    assert rows[0]["source_language"] == "ko"
    assert rows[0]["target_language"] == "vi"
    assert rows[0]["verdict"] == "incorrect"
    assert rows[0]["correction"] == "The Vietnamese translation lost the uncertainty."
    assert rows[0]["reviewer_role"] == "author"


def test_fact_check_feedback_export_includes_the_reviewed_excerpt(tmp_path: Path) -> None:
    path = tmp_path / "test.sqlite3"
    store = Store(path)
    store.initialize()
    analysis = store.create_analysis()
    fact_check, _ = store.create_or_get_fact_check(analysis.id)
    claim = ClaimCandidate(
        id="claim-1",
        source_quote="The agency reported 24 buses.",
        segment_ids=["p1s1"],
        standalone_claim="The agency reported 24 buses.",
        claim_type=ClaimType.ATTRIBUTED,
        reason="A checkable figure.",
    )
    evidence = EvidenceItem(
        id="evidence-1",
        url="https://source.example/report",
        publisher="Source Desk",
        publisher_key="source.example",
        language=Language.ENGLISH,
        excerpt="The agency said the trial includes 24 buses.",
        source_type=EvidenceSourceKind.DIRECT_REPORTING,
        retrieved_at="2026-07-24T09:55:00Z",
        content_hash="hash",
        cluster_id="cluster",
        relevance=0.9,
    )
    store.update_fact_check(
        fact_check.id,
        status=FactCheckStatus.COMPLETE,
        stage="Ready",
        progress=100,
        result=FactCheckResult(
            checked_at="2026-07-24T10:00:00Z",
            claims=[
                ClaimCheckResult(
                    claim=claim,
                    evidence=[evidence],
                    assessment=ClaimAssessment(
                        claim_id=claim.id,
                        status=ClaimEvidenceStatus.INSUFFICIENT,
                        explanation="One source is not enough.",
                    ),
                )
            ],
        ),
    )
    store.add_fact_check_feedback(
        fact_check.id,
        FactCheckFeedbackCreate(
            target_type=FactCheckFeedbackTarget.EVIDENCE,
            target_id=evidence.id,
            verdict=FeedbackVerdict.INCORRECT,
            correction="This concerns a different trial.",
            better_source_url="https://primary.example/record",
        ),
    )
    output = StringIO()

    write_fact_check_feedback(path, output)
    rows = list(csv.DictReader(StringIO(output.getvalue())))

    assert len(rows) == 1
    assert rows[0]["claim_id"] == "claim-1"
    assert rows[0]["evidence_excerpt"] == evidence.excerpt
    assert rows[0]["verdict"] == "incorrect"
    assert rows[0]["better_source_url"] == "https://primary.example/record"
