import importlib.util
import json
from collections import Counter
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_claim_trace_closed_set.py"
MANIFEST = Path(__file__).parents[1] / "evaluation" / "claim-trace-corpus.json"


def _module():
    spec = importlib.util.spec_from_file_location("closed_set_runner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_closed_set_pilot_is_balanced_across_topics_and_languages() -> None:
    module = _module()
    cases = module.load_pilot_cases(json.loads(MANIFEST.read_text()))

    assert len(cases) == 6
    assert len({case["event"]["topic"] for case in cases}) == 6
    assert Counter(case["seed_language"] for case in cases) == {
        "en": 2,
        "ko": 2,
        "vi": 2,
    }
    assert all(case["source_article"]["source_language"] == case["seed_language"] for case in cases)


def test_full_closed_set_uses_all_frozen_cases() -> None:
    module = _module()
    cases = module.load_cases(json.loads(MANIFEST.read_text()), "full")

    assert len(cases) == 24
    assert Counter(case["seed_language"] for case in cases) == {
        "en": 8,
        "ko": 8,
        "vi": 8,
    }
    assert {case["event"]["profile"] for case in cases} == {"clean", "challenging"}
    assert all(case["source_article"]["source_language"] == case["seed_language"] for case in cases)


def test_evidence_summary_does_not_store_article_excerpt() -> None:
    module = _module()
    from app.models import (
        EvidenceItem,
        EvidenceSourceKind,
        Language,
    )

    item = EvidenceItem(
        id="evidence",
        url="https://example.com/report",
        publisher="Example",
        language=Language.ENGLISH,
        excerpt="Copyrighted article body is not retained in the pilot output.",
        source_type=EvidenceSourceKind.DIRECT_REPORTING,
        content_hash="hash",
        cluster_id="cluster",
        relevance=0.9,
    )

    summary = module._evidence_summary(item)

    assert "excerpt" not in summary
