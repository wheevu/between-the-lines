from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
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
    EvidenceStance,
    FactCheckResult,
    FactCheckStatus,
)
from app.store import Store


class FakeAnalyzer:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(self, analysis_id, request) -> None:
        self.store.update_analysis(
            analysis_id,
            status=AnalysisStatus.COMPLETE,
            stage="Ready to review",
            progress=100,
            result=AnalysisResult(source_language=request.source_language, segments=[]),
        )


class FakeClaimExtractor:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(self, fact_check_id: str) -> None:
        self.store.update_fact_check(
            fact_check_id,
            status=FactCheckStatus.AWAITING_SELECTION,
            stage="Choose claims to check",
            progress=100,
            candidates=[
                ClaimCandidate(
                    id="claim-1",
                    source_quote="A short article.",
                    segment_ids=["p1s1"],
                    standalone_claim="A short article.",
                    claim_type=ClaimType.FACT,
                    reason="A test claim.",
                ),
                ClaimCandidate(
                    id="claim-opinion",
                    source_quote="A short article.",
                    segment_ids=["p1s1"],
                    standalone_claim="A short article.",
                    claim_type=ClaimType.UNSUITABLE,
                    reason="This is an opinion.",
                ),
            ],
        )


class FakeFactChecker:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(self, fact_check_id: str) -> None:
        candidate = ClaimCandidate(
            id="claim-1",
            source_quote="A short article.",
            segment_ids=["p1s1"],
            standalone_claim="A short article.",
            claim_type=ClaimType.FACT,
            reason="A test claim.",
        )
        self.store.update_fact_check(
            fact_check_id,
            status=FactCheckStatus.COMPLETE,
            stage="Evidence ready to inspect",
            progress=100,
            result=FactCheckResult(
                checked_at="2026-07-24T00:00:00Z",
                claims=[
                    ClaimCheckResult(
                        claim=candidate,
                        evidence=[
                            EvidenceItem(
                                id="evidence-1",
                                url="https://source.example/report",
                                publisher="Source",
                                language="en",
                                excerpt="A relevant source excerpt.",
                                source_type=EvidenceSourceKind.DIRECT_REPORTING,
                                retrieved_at="2026-07-24T00:00:00Z",
                                content_hash="hash",
                                cluster_id="cluster",
                                relevance=0.9,
                                stance=EvidenceStance.SUPPORTS,
                            )
                        ],
                        assessment=ClaimAssessment(
                            claim_id=candidate.id,
                            status=ClaimEvidenceStatus.INSUFFICIENT,
                            explanation="One source is not enough.",
                        ),
                    )
                ],
            ),
        )


def test_analysis_and_feedback_http_flow(monkeypatch, tmp_path: Path) -> None:
    store = Store(tmp_path / "api.sqlite3")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "analyzer", FakeAnalyzer(store))
    monkeypatch.setattr(main, "claim_extractor", FakeClaimExtractor(store))

    with TestClient(main.app) as client:
        health = client.get("/api/health")
        created = client.post(
            "/api/analyses",
            json={"source_language": "en", "text": "A short article."},
        )
        analysis_id = created.json()["id"]
        completed = client.get(f"/api/analyses/{analysis_id}")
        feedback = client.post(
            f"/api/analyses/{analysis_id}/feedback",
            json={"flag_id": "flag-1", "verdict": "helpful"},
        )
        fact_check = client.post(f"/api/analyses/{analysis_id}/fact-checks")
        fact_check_id = fact_check.json()["id"]
        extracted = client.get(f"/api/fact-checks/{fact_check_id}")
        same_fact_check = client.post(f"/api/analyses/{analysis_id}/fact-checks")
        rejected_multiple = client.post(
            f"/api/fact-checks/{fact_check_id}/selection",
            json={"candidate_ids": ["claim-1", "claim-opinion"]},
        )
        selected = client.post(
            f"/api/fact-checks/{fact_check_id}/selection",
            json={"candidate_ids": ["claim-1"]},
        )
        rejected_opinion = client.post(
            f"/api/fact-checks/{fact_check_id}/selection",
            json={"candidate_ids": ["claim-opinion"]},
        )

    assert health.json() == {"status": "ok"}
    assert created.status_code == 202
    assert completed.json()["status"] == "complete"
    assert feedback.status_code == 200
    assert feedback.json()["analysis_id"] == analysis_id
    assert fact_check.status_code == 202
    assert fact_check.json()["status"] == "extracting_claims"
    assert extracted.json()["status"] == "awaiting_selection"
    assert same_fact_check.json()["id"] == fact_check_id
    assert rejected_multiple.status_code == 422
    assert selected.json()["selected_candidate_ids"] == ["claim-1"]
    assert rejected_opinion.status_code == 422


def test_analysis_accepts_one_target_and_rejects_the_source_language(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "api.sqlite3")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "analyzer", FakeAnalyzer(store))

    with TestClient(main.app) as client:
        accepted = client.post(
            "/api/analyses",
            json={
                "source_language": "en",
                "target_language": "ko",
                "text": "A short article.",
            },
        )
        rejected = client.post(
            "/api/analyses",
            json={
                "source_language": "en",
                "target_language": "en",
                "text": "A short article.",
            },
        )

    assert accepted.status_code == 202
    assert rejected.status_code == 422
    assert "different" in rejected.text


def test_fact_check_requires_a_completed_analysis(monkeypatch, tmp_path: Path) -> None:
    store = Store(tmp_path / "api.sqlite3")
    monkeypatch.setattr(main, "store", store)

    with TestClient(main.app) as client:
        job = store.create_analysis()
        response = client.post(f"/api/analyses/{job.id}/fact-checks")

    assert response.status_code == 409
    assert response.json()["detail"] == "Finish the article analysis before choosing claims."


def test_ready_gate_starts_evidence_worker_and_repeated_selection_is_idempotent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "api.sqlite3")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "analyzer", FakeAnalyzer(store))
    monkeypatch.setattr(main, "claim_extractor", FakeClaimExtractor(store))
    monkeypatch.setattr(main, "fact_checker", FakeFactChecker(store))
    monkeypatch.setattr(
        main,
        "summarize_database",
        lambda _: {"ready_for_evidence_layer_decision": True},
    )

    with TestClient(main.app) as client:
        analysis = client.post(
            "/api/analyses",
            json={"source_language": "en", "text": "A short article."},
        ).json()
        fact_check = client.post(f"/api/analyses/{analysis['id']}/fact-checks").json()
        started = client.post(
            f"/api/fact-checks/{fact_check['id']}/selection",
            json={"candidate_ids": ["claim-1"]},
        )
        completed = client.get(f"/api/fact-checks/{fact_check['id']}")
        repeated = client.post(
            f"/api/fact-checks/{fact_check['id']}/selection",
            json={"candidate_ids": ["claim-1"]},
        )
        changed = client.post(
            f"/api/fact-checks/{fact_check['id']}/selection",
            json={"candidate_ids": ["claim-opinion"]},
        )
        evidence_feedback = client.post(
            f"/api/fact-checks/{fact_check['id']}/feedback",
            json={
                "target_type": "evidence",
                "target_id": "evidence-1",
                "verdict": "helpful",
            },
        )
        status_feedback = client.post(
            f"/api/fact-checks/{fact_check['id']}/feedback",
            json={
                "target_type": "status",
                "target_id": "claim-1",
                "verdict": "incorrect",
                "correction": "This should remain unresolved.",
            },
        )
        invented_target = client.post(
            f"/api/fact-checks/{fact_check['id']}/feedback",
            json={
                "target_type": "evidence",
                "target_id": "invented",
                "verdict": "helpful",
            },
        )

    assert started.json()["status"] == "retrieving"
    assert completed.json()["status"] == "complete"
    assert repeated.json()["status"] == "complete"
    assert changed.status_code == 409
    assert evidence_feedback.status_code == 200
    assert evidence_feedback.json()["target_id"] == "evidence-1"
    assert status_feedback.status_code == 200
    assert invented_target.status_code == 422
