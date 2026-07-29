import json
from collections import Counter
from pathlib import Path

from app.models import Language

FIXTURE = Path(__file__).parents[1] / "evaluation" / "risk-rich-excerpts.json"


def test_risk_rich_excerpts_are_authored_balanced_and_reviewable() -> None:
    data = json.loads(FIXTURE.read_text())
    cases = data["cases"]
    languages = Counter(Language(case["source_language"]) for case in cases)

    assert "Synthetic passages authored" in data["provenance"]
    assert languages == {
        Language.ENGLISH: 1,
        Language.VIETNAMESE: 1,
        Language.KOREAN: 1,
    }
    assert all(150 <= len(case["text"].split()) <= 300 for case in cases)
