from pathlib import Path

import pytest

import app.analyzer as analyzer_module
from app.analyzer import Analyzer, _public_error
from app.config import Settings
from app.gemini import GeminiTranslationError
from app.models import (
    AmbiguityCategory,
    AnalysisCreate,
    AnalysisStatus,
    GeminiNote,
    GeminiTranslation,
    Language,
)
from app.store import Store


class FakeGemini:
    def translate(self, segments, source_language, target_language):
        del source_language
        suffix = {Language.ENGLISH: " EN", Language.VIETNAMESE: " VI", Language.KOREAN: " KO"}
        return [
            GeminiTranslation(
                segment_id=segment.id,
                translation=f"{segment.text}{suffix[target_language]}",
                notes=[
                    GeminiNote(
                        source_quote="may",
                        translation_quote="may",
                        category=AmbiguityCategory.MODALITY,
                        explanation="Certainty can shift here.",
                    )
                ]
                if "may" in segment.text
                else [],
            )
            for segment in segments
        ]


def test_analyzer_completes_all_target_languages(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    job = store.create_analysis()
    analyzer = Analyzer(
        settings=Settings(
            gemini_api_key="test",
            gemini_model="test",
            database_path=tmp_path / "test.sqlite3",
        ),
        store=store,
        gemini=FakeGemini(),
    )

    analyzer.run(
        job.id,
        AnalysisCreate(source_language=Language.ENGLISH, text="The policy may change."),
    )

    completed = store.get_analysis(job.id)
    assert completed is not None
    assert completed.status is AnalysisStatus.COMPLETE
    assert completed.result is not None
    assert [item.language for item in completed.result.segments[0].translations] == [
        Language.VIETNAMESE,
        Language.KOREAN,
    ]


def test_analyzer_reuses_a_completed_analysis(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    gemini = FakeGemini()
    calls = 0
    original_translate = gemini.translate

    def counted_translate(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_translate(*args, **kwargs)

    gemini.translate = counted_translate
    analyzer = Analyzer(
        settings=Settings(
            gemini_api_key="test",
            gemini_model="test",
            database_path=tmp_path / "test.sqlite3",
        ),
        store=store,
        gemini=gemini,
    )
    request = AnalysisCreate(source_language=Language.ENGLISH, text="The policy may change.")

    first = store.create_analysis()
    analyzer.run(first.id, request)
    second = store.create_analysis()
    analyzer.run(second.id, request)

    assert calls == 2
    assert store.get_analysis(second.id).status is AnalysisStatus.COMPLETE


def test_analyzer_translates_only_requested_target_without_blocking_shadow_pass(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    job = store.create_analysis()
    analyzer = Analyzer(
        settings=Settings(
            gemini_api_key="test",
            gemini_model="test",
            database_path=tmp_path / "test.sqlite3",
        ),
        store=store,
        gemini=FakeGemini(),
    )
    text = (
        "Opening sentence. Another lead sentence. Plain background follows. "
        "The court may rule on 12 August."
    )

    analyzer.run(
        job.id,
        AnalysisCreate(
            source_language=Language.ENGLISH,
            target_language=Language.VIETNAMESE,
            text=text,
        ),
    )

    completed = store.get_analysis(job.id)
    assert completed is not None and completed.result is not None
    translations = [
        translation for segment in completed.result.segments for translation in segment.translations
    ]
    assert {item.language for item in translations} == {Language.VIETNAMESE}
    assert all(item.shadow_text is None for item in translations)
    assert all(item.similarity is None for item in translations)


def test_analysis_rejects_matching_source_and_target() -> None:
    try:
        AnalysisCreate(
            source_language=Language.KOREAN,
            target_language=Language.KOREAN,
            text="기사 본문",
        )
    except ValueError as error:
        assert "different" in str(error)
    else:
        raise AssertionError("matching source and target should fail")


def test_analysis_rejects_fallback_url_without_pasted_text() -> None:
    try:
        AnalysisCreate(
            source_language=Language.ENGLISH,
            target_language=Language.VIETNAMESE,
            fallback_url="https://example.com/article",
        )
    except ValueError as error:
        assert "either article text or a URL" in str(error)
    else:
        raise AssertionError("a fallback URL without text should fail")


def test_analyzer_keeps_fallback_page_link_for_pasted_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    job = store.create_analysis()
    analyzer = Analyzer(
        settings=Settings(
            gemini_api_key="test",
            gemini_model="test",
            database_path=tmp_path / "test.sqlite3",
        ),
        store=store,
        gemini=FakeGemini(),
    )
    monkeypatch.setattr(
        analyzer_module,
        "extract_metadata",
        lambda url: ("https://example.com/article", "A readable report"),
    )

    analyzer.run(
        job.id,
        AnalysisCreate(
            source_language=Language.ENGLISH,
            target_language=Language.VIETNAMESE,
            text="The policy may change next month.",
            fallback_url="https://example.com/article",
        ),
    )

    completed = store.get_analysis(job.id)
    assert completed is not None and completed.result is not None
    assert completed.result.source_title == "A readable report"
    assert completed.result.source_url == "https://example.com/article"


def test_analyzer_keeps_pasted_text_when_fallback_metadata_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    job = store.create_analysis()
    analyzer = Analyzer(
        settings=Settings(
            gemini_api_key="test",
            gemini_model="test",
            database_path=tmp_path / "test.sqlite3",
        ),
        store=store,
        gemini=FakeGemini(),
    )
    monkeypatch.setattr(analyzer_module, "extract_metadata", lambda url: (None, None))

    analyzer.run(
        job.id,
        AnalysisCreate(
            source_language=Language.ENGLISH,
            target_language=Language.VIETNAMESE,
            text="The policy may change next month.",
            fallback_url="https://example.com/article",
        ),
    )

    completed = store.get_analysis(job.id)
    assert completed is not None
    assert completed.status is AnalysisStatus.COMPLETE
    assert completed.result is not None
    assert completed.result.source_title is None
    assert completed.result.source_url is None


def test_gemini_service_errors_are_safe_to_show_to_the_user() -> None:
    message = "Gemini's request quota is exhausted. Try again after it resets."

    assert _public_error(GeminiTranslationError(message)) == message
