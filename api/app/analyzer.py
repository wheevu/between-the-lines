import logging
from hashlib import sha256

from app.ambiguity import build_flags
from app.article import extract_article, extract_metadata
from app.config import Settings
from app.gemini import GeminiTranslationError, GeminiTranslator
from app.models import (
    AnalysisCreate,
    AnalysisResult,
    AnalysisStatus,
    Language,
    SegmentResult,
    TargetTranslation,
)
from app.segmentation import segment_article
from app.store import Store

TARGET_LANGUAGES = {
    Language.ENGLISH: (Language.VIETNAMESE, Language.KOREAN),
    Language.VIETNAMESE: (Language.ENGLISH, Language.KOREAN),
    Language.KOREAN: (Language.ENGLISH, Language.VIETNAMESE),
}

logger = logging.getLogger(__name__)


class Analyzer:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        gemini: GeminiTranslator,
    ) -> None:
        self.settings = settings
        self.store = store
        self.gemini = gemini

    def run(self, analysis_id: str, request: AnalysisCreate) -> None:
        try:
            result = self._analyze(analysis_id, request)
            self.store.update_analysis(
                analysis_id,
                status=AnalysisStatus.COMPLETE,
                stage="Ready to review",
                progress=100,
                result=result,
            )
        except Exception as error:
            logger.exception("Analysis %s failed", analysis_id)
            self.store.update_analysis(
                analysis_id,
                status=AnalysisStatus.FAILED,
                stage="Analysis stopped",
                progress=100,
                error=_public_error(error),
            )

    def _analyze(self, analysis_id: str, request: AnalysisCreate) -> AnalysisResult:
        source_title = None
        source_url = None
        if request.url:
            self._progress(analysis_id, AnalysisStatus.EXTRACTING, "Reading the article", 5)
            article = extract_article(str(request.url), self.settings)
            source_title = article.title
            source_url = article.url
            text = article.text
        else:
            text = request.text or ""
            if request.fallback_url is not None:
                # The URL failed full extraction, but its link can still be
                # kept when the reader pastes the article text instead.
                source_url, source_title = extract_metadata(str(request.fallback_url))

        if len(text.split()) > self.settings.max_article_words:
            raise ValueError(f"Keep the article under {self.settings.max_article_words:,} words.")
        cache_key = _cache_key(
            text=text,
            source_language=request.source_language,
            target_language=request.target_language,
            source_title=source_title,
            source_url=source_url,
            gemini_model=self.settings.gemini_model,
        )
        cached = self.store.get_cached_result(cache_key)
        if cached is not None:
            return cached

        segments = segment_article(text, request.source_language)
        if not segments:
            raise ValueError("Add some article text before translating.")

        target_languages = (
            (request.target_language,)
            if request.target_language is not None
            else TARGET_LANGUAGES[request.source_language]
        )
        primary_by_language = {}
        for index, target_language in enumerate(target_languages):
            self._progress(
                analysis_id,
                AnalysisStatus.TRANSLATING,
                f"Translating into {target_language.value.upper()}",
                15 + index * 20,
            )
            primary_by_language[target_language] = self.gemini.translate(
                segments, request.source_language, target_language
            )

        results = [
            SegmentResult(
                id=segment.id,
                paragraph_index=segment.paragraph_index,
                sentence_index=segment.sentence_index,
                source_text=segment.text,
                translations=[],
            )
            for segment in segments
        ]
        source_texts = [segment.text for segment in segments]

        for index, target_language in enumerate(target_languages):
            self._progress(
                analysis_id,
                AnalysisStatus.ANALYZING,
                f"Checking the {target_language.value.upper()} translation",
                55 + index * 20,
            )
            primary = primary_by_language[target_language]
            for item_index, translation in enumerate(primary):
                results[item_index].translations.append(
                    TargetTranslation(
                        language=target_language,
                        text=translation.translation,
                        shadow_text=None,
                        similarity=None,
                        back_translation_similarity=None,
                        flags=build_flags(
                            source_text=source_texts[item_index],
                            primary_text=translation.translation,
                            target_language=target_language,
                            source_language=request.source_language,
                            notes=translation.notes,
                            shadow_similarity=None,
                            back_translation_similarity=None,
                        ),
                    )
                )

        result = AnalysisResult(
            source_language=request.source_language,
            source_title=source_title,
            source_url=source_url,
            segments=results,
        )
        self.store.cache_result(cache_key, result)
        return result

    def _progress(
        self,
        analysis_id: str,
        status: AnalysisStatus,
        stage: str,
        progress: int,
    ) -> None:
        self.store.update_analysis(
            analysis_id,
            status=status,
            stage=stage,
            progress=progress,
        )


def _public_error(error: Exception) -> str:
    if isinstance(error, (GeminiTranslationError, ValueError)):
        return str(error)
    return "The analysis couldn't finish. Check the API logs and try again."


def _cache_key(
    *,
    text: str,
    source_language: Language,
    target_language: Language | None,
    source_title: str | None,
    source_url: str | None,
    gemini_model: str,
) -> str:
    payload = "\n".join(
        (
            "analysis-v14",
            gemini_model,
            source_language.value,
            target_language.value if target_language else "all",
            source_title or "",
            source_url or "",
            text,
        )
    )
    return sha256(payload.encode()).hexdigest()
