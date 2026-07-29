import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from app.ambiguity import extract_number_anchors
from app.models import ClaimCandidate, Language

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
MANIFEST = EVALUATION_DIR / "newjeans-corpus.json"
POOL = EVALUATION_DIR / "newjeans-claim-pool.json"


def test_newjeans_claim_pool_is_complete_balanced_and_source_grounded() -> None:
    manifest = json.loads(MANIFEST.read_text())
    data = json.loads(POOL.read_text())
    manifest_by_id = {case["id"]: case for case in manifest["cases"]}
    candidate_ids = []

    assert data["complete"]
    assert data["pipeline_version"] == 2
    assert data["stopped_at"] is None
    assert data["error"] is None
    assert data["manifest_sha256"] == sha256(MANIFEST.read_bytes()).hexdigest()
    assert datetime.fromisoformat(data["updated_at"]).tzinfo is not None
    assert len(data["cases"]) == 15
    assert Counter(case["source_language"] for case in data["cases"]) == {
        "en": 5,
        "vi": 5,
        "ko": 5,
    }

    for case in data["cases"]:
        assert case["id"] in manifest_by_id
        assert 3 <= len(case["candidates"]) <= 5
        assert len(case["source_sha256"]) == 64
        language = Language(case["source_language"])
        for raw_candidate in case["candidates"]:
            candidate = ClaimCandidate.model_validate(raw_candidate)
            candidate_ids.append(candidate.id)
            assert extract_number_anchors(
                candidate.standalone_claim,
                language,
            ).issubset(extract_number_anchors(candidate.source_quote, language))

    assert len(candidate_ids) == len(set(candidate_ids))
