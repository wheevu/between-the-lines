from types import SimpleNamespace

import pytest

from app.models import (
    ClaimCandidate,
    ClaimType,
    GeminiQueryBatch,
    Language,
    SearchQuery,
)
from app.query_generator import QueryGenerationError, QueryGenerator, _query_prompt


def claim() -> ClaimCandidate:
    return ClaimCandidate(
        id="claim-1",
        source_quote="ADOR said the trial may begin on 12 October.",
        segment_ids=["p1s1"],
        standalone_claim="ADOR said the trial may begin on 12 October.",
        claim_type=ClaimType.ATTRIBUTED,
        entities=["ADOR"],
        dates=["12 October"],
        reason="A dated attributed statement.",
    )


def query(language: Language) -> SearchQuery:
    return SearchQuery(
        language=language,
        exact_query=f"ADOR 12 October {language.value}",
        context_query=f"ADOR trial may begin {language.value}",
    )


class FakeModels:
    def __init__(self, queries: list[SearchQuery]) -> None:
        self.queries = queries

    def generate_content(self, *, model, contents, config):
        del model, contents, config
        return SimpleNamespace(parsed=GeminiQueryBatch(queries=self.queries))


def test_query_prompt_preserves_attribution_and_treats_claim_as_untrusted() -> None:
    prompt = _query_prompt(claim())

    assert "attributed claim" in prompt
    assert "do not rewrite the allegation as an established event" in prompt
    assert "untrusted" in prompt
    assert "12 October" in prompt


def test_query_generator_returns_one_query_pair_per_language() -> None:
    generator = QueryGenerator("key", "model")
    generator.client = SimpleNamespace(
        models=FakeModels(
            [query(Language.KOREAN), query(Language.ENGLISH), query(Language.VIETNAMESE)]
        )
    )

    queries = generator.generate(claim())

    assert [item.language for item in queries] == list(Language)


def test_query_generator_rejects_duplicate_language_entries() -> None:
    generator = QueryGenerator("key", "model")
    generator.client = SimpleNamespace(
        models=FakeModels(
            [query(Language.ENGLISH), query(Language.ENGLISH), query(Language.KOREAN)]
        )
    )

    with pytest.raises(QueryGenerationError, match="one query set per language"):
        generator.generate(claim())


def test_query_generator_rejects_a_language_that_drops_a_numeric_anchor() -> None:
    generator = QueryGenerator("key", "model")
    missing_date = query(Language.KOREAN).model_copy(
        update={
            "exact_query": "ADOR October ko",
            "context_query": "ADOR trial may begin ko",
        }
    )
    generator.client = SimpleNamespace(
        models=FakeModels([query(Language.ENGLISH), query(Language.VIETNAMESE), missing_date])
    )

    with pytest.raises(QueryGenerationError, match="KO queries dropped"):
        generator.generate(claim())


def test_query_validation_uses_numbers_in_the_standalone_claim() -> None:
    candidate = claim().model_copy(update={"dates": []})
    generator = QueryGenerator("key", "model")
    missing_date = query(Language.KOREAN).model_copy(
        update={
            "exact_query": "ADOR October ko",
            "context_query": "ADOR trial may begin ko",
        }
    )
    generator.client = SimpleNamespace(
        models=FakeModels([query(Language.ENGLISH), query(Language.VIETNAMESE), missing_date])
    )

    with pytest.raises(QueryGenerationError, match="KO queries dropped"):
        generator.generate(candidate)


def test_query_generation_requires_cloud_configuration() -> None:
    generator = QueryGenerator(None, "model")

    with pytest.raises(QueryGenerationError, match="isn't configured"):
        generator.generate(claim())
