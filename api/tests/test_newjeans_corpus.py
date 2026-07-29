import json
from collections import Counter
from pathlib import Path

MANIFEST = Path(__file__).parents[1] / "evaluation" / "newjeans-corpus.json"


def test_newjeans_corpus_has_five_articles_per_language() -> None:
    data = json.loads(MANIFEST.read_text())
    cases = data["cases"]

    assert len(cases) == 15
    assert Counter(case["source_language"] for case in cases) == {
        "en": 5,
        "vi": 5,
        "ko": 5,
    }
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["url"].startswith("https://") for case in cases)
    assert sum("analysis_id" in case for case in cases) == 6
