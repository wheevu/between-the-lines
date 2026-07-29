import json
from collections import Counter
from datetime import date
from pathlib import Path

from app.models import Language

MANIFEST = Path(__file__).parents[1] / "evaluation" / "cross-domain-smoke.json"


def test_cross_domain_manifest_is_balanced_recent_and_bounded() -> None:
    data = json.loads(MANIFEST.read_text())
    cases = data["cases"]
    languages = Counter(Language(case["source_language"]) for case in cases)
    cutoff = date(2026, 1, 24)

    assert len(cases) == 6
    assert languages == {
        Language.ENGLISH: 2,
        Language.VIETNAMESE: 2,
        Language.KOREAN: 2,
    }
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(date.fromisoformat(case["published"]) >= cutoff for case in cases)
    assert all(40 <= case["verified_extracted_words"] <= 2_500 for case in cases)
