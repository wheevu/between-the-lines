import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from app.ambiguity import extract_number_anchors
from app.models import ClaimCandidate, Language

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
MANIFEST = EVALUATION_DIR / "cross-domain-smoke.json"
CANDIDATES = EVALUATION_DIR / "cross-domain-claim-candidates.json"


def test_frozen_cross_domain_candidates_are_balanced_and_grounded() -> None:
    manifest = json.loads(MANIFEST.read_text())
    data = json.loads(CANDIDATES.read_text())
    manifest_cases = {case["id"]: case for case in manifest["cases"]}
    candidate_ids: list[str] = []

    assert data["schema_version"] == 1
    assert data["pipeline_version"] == 2
    assert data["manifest_sha256"] == sha256(MANIFEST.read_bytes()).hexdigest()
    assert datetime.fromisoformat(data["generated_at"]).tzinfo is not None
    assert {case["id"] for case in data["cases"]} == set(manifest_cases)
    assert Counter(case["source_language"] for case in data["cases"]) == {
        "en": 2,
        "vi": 2,
        "ko": 2,
    }

    for case in data["cases"]:
        # The extractor may return fewer than the requested three rather than
        # retain a candidate that fails deterministic grounding checks.
        assert 2 <= len(case["candidates"]) <= 5
        assert len(case["source_sha256"]) == 64
        assert case["source_language"] == manifest_cases[case["id"]]["source_language"]
        language = Language(case["source_language"])
        for raw_candidate in case["candidates"]:
            candidate = ClaimCandidate.model_validate(raw_candidate)
            candidate_ids.append(candidate.id)
            assert candidate.source_quote
            assert candidate.standalone_claim
            assert extract_number_anchors(
                candidate.standalone_claim,
                language,
            ).issubset(extract_number_anchors(candidate.source_quote, language))

    assert len(candidate_ids) == len(set(candidate_ids))
