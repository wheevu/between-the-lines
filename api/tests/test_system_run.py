import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.models import (
    ClaimAssessment,
    ClaimCheckResult,
    ClaimEvidenceStatus,
)
from app.system_run import load_frozen_claims, run_frozen_claims


class FakeChecker:
    def __init__(self, *, quota_on: set[str] | None = None) -> None:
        self.quota_on = quota_on or set()
        self.calls: list[str] = []

    def check_claim(self, claim, *, input_url):
        assert input_url.startswith("https://")
        self.calls.append(claim.id)
        if claim.id in self.quota_on:
            reason = "Gemini's request quota is exhausted. Try again after it resets."
            return ClaimCheckResult(
                claim=claim,
                assessment=ClaimAssessment(
                    claim_id=claim.id,
                    status=ClaimEvidenceStatus.INSUFFICIENT,
                    explanation="Evidence search could not be completed for this claim.",
                    limitations=[reason],
                ),
                error=reason,
            )
        return ClaimCheckResult(
            claim=claim,
            assessment=ClaimAssessment(
                claim_id=claim.id,
                status=ClaimEvidenceStatus.INSUFFICIENT,
                explanation="No relevant, readable evidence was found for this claim.",
                limitations=[],
            ),
        )


def test_frozen_run_checkpoints_and_resumes_without_repeating_claims(
    tmp_path: Path,
) -> None:
    adjudication, pool, corpus = _write_inputs(tmp_path)
    claims = load_frozen_claims(adjudication, pool, corpus)
    output = tmp_path / "system-results.json"
    checker = FakeChecker()

    partial = run_frozen_claims(
        checker,
        claims,
        output,
        identity=_identity(adjudication),
        max_new_claims=2,
    )
    completed = run_frozen_claims(
        checker,
        claims,
        output,
        identity=_identity(adjudication),
    )

    assert not partial["complete"]
    assert partial["pause_reason"] == "Invocation claim limit reached."
    assert len(partial["claims"]) == 2
    assert completed["complete"]
    assert len(completed["claims"]) == 30
    assert len(checker.calls) == 30
    assert len(set(checker.calls)) == 30
    with pytest.raises(ValueError, match="already complete"):
        run_frozen_claims(
            checker,
            claims,
            output,
            identity=_identity(adjudication),
        )


def test_quota_failure_is_recorded_but_not_scored_as_a_claim(tmp_path: Path) -> None:
    adjudication, pool, corpus = _write_inputs(tmp_path)
    claims = load_frozen_claims(adjudication, pool, corpus)
    output = tmp_path / "system-results.json"

    paused = run_frozen_claims(
        FakeChecker(quota_on={"claim-0"}),
        claims,
        output,
        identity=_identity(adjudication),
    )

    assert not paused["complete"]
    assert paused["claims"] == []
    assert paused["stopped_at"] == "claim-0"
    assert "quota is exhausted" in paused["pause_reason"]
    assert paused["attempt_failures"][0]["candidate_id"] == "claim-0"

    resumed_checker = FakeChecker()
    completed = run_frozen_claims(
        resumed_checker,
        claims,
        output,
        identity=_identity(adjudication),
    )

    assert completed["complete"]
    assert len(resumed_checker.calls) == 30


def test_changed_input_identity_or_claim_text_cannot_resume(tmp_path: Path) -> None:
    adjudication, pool, corpus = _write_inputs(tmp_path)
    claims = load_frozen_claims(adjudication, pool, corpus)
    output = tmp_path / "system-results.json"
    run_frozen_claims(
        FakeChecker(),
        claims,
        output,
        identity=_identity(adjudication),
        max_new_claims=1,
    )

    with pytest.raises(ValueError, match="different frozen inputs"):
        run_frozen_claims(
            FakeChecker(),
            claims,
            output,
            identity={**_identity(adjudication), "pipeline_sha256": "changed"},
        )

    data = json.loads(adjudication.read_text())
    data["claims"][0]["standalone_claim"] = "The adjudicated text was changed."
    adjudication.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="changed from the frozen pool"):
        load_frozen_claims(adjudication, pool, corpus)


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    corpus = tmp_path / "corpus.json"
    pool = tmp_path / "pool.json"
    adjudication = tmp_path / "gold.json"
    corpus_cases = [
        {
            "id": f"{language}-case",
            "source_language": language,
            "publisher": f"{language.upper()} Publisher",
            "url": f"https://{language}.example/article",
        }
        for language in ("en", "vi", "ko")
    ]
    corpus.write_text(json.dumps({"cases": corpus_cases}))
    pool_cases = []
    gold_claims = []
    for language_index, case in enumerate(corpus_cases):
        candidates = []
        for local_index in range(10):
            index = language_index * 10 + local_index
            candidate = {
                "id": f"claim-{index}",
                "source_quote": f"Exact quote {index}.",
                "segment_ids": [f"p{local_index + 1}s1"],
                "standalone_claim": f"Standalone claim {index}.",
                "claim_type": "fact",
                "entities": [],
                "dates": [],
                "numbers": [],
                "reason": "Frozen evaluation claim.",
            }
            candidates.append(candidate)
            gold_claims.append(
                {
                    "candidate_id": candidate["id"],
                    "case_id": case["id"],
                    "source_language": case["source_language"],
                    "claim_type": candidate["claim_type"],
                    "source_quote": candidate["source_quote"],
                    "standalone_claim": candidate["standalone_claim"],
                }
            )
        pool_cases.append({**case, "candidates": candidates})
    pool.write_text(
        json.dumps(
            {
                "complete": True,
                "manifest_sha256": sha256(corpus.read_bytes()).hexdigest(),
                "cases": pool_cases,
            }
        )
    )
    adjudication.write_text(json.dumps({"claims": gold_claims}))
    return adjudication, pool, corpus


def _identity(adjudication: Path) -> dict[str, object]:
    return {
        "adjudication_sha256": sha256(adjudication.read_bytes()).hexdigest(),
        "pipeline_sha256": "pipeline",
        "gemini_model": "test-model",
        "embedding_backend": "torch",
    }
