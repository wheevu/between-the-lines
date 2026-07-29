import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.article import extract_article
from app.claim_extractor import ClaimExtractor
from app.config import Settings, load_settings
from app.models import AnalysisResult, Language, SegmentResult
from app.segmentation import segment_article
from app.store import Store

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
MANIFEST = EVALUATION_DIR / "newjeans-corpus.json"
OUTPUT = EVALUATION_DIR / "newjeans-claim-pool.json"
PIPELINE_VERSION = 2


def main() -> int:
    settings = load_settings()
    store = Store(settings.database_path)
    store.initialize()
    extractor = ClaimExtractor(
        store,
        settings.gemini_api_key,
        settings.gemini_model,
    )
    manifest = json.loads(MANIFEST.read_text())
    manifest_sha = sha256(MANIFEST.read_bytes()).hexdigest()
    existing = _existing_cases(settings.gemini_model, manifest_sha)
    completed: list[dict[str, object]] = []

    for case in manifest["cases"]:
        result, source_hash, source_title, extracted_words = _load_case(
            case,
            store,
            settings,
        )
        previous = existing.get(case["id"])
        if previous and previous.get("source_sha256") == source_hash and previous.get("candidates"):
            completed.append(previous)
            print(f"{case['id']}: reused {len(previous['candidates'])} candidates")
            continue
        try:
            candidates = extractor.extract(result)
        except Exception as error:
            _write_output(
                settings.gemini_model,
                manifest_sha,
                completed,
                complete=False,
                stopped_at=case["id"],
                error=str(error),
            )
            print(f"{case['id']}: stopped — {error}")
            return 1
        completed.append(
            {
                "id": case["id"],
                "source_language": case["source_language"],
                "publisher": case["publisher"],
                "url": case["url"],
                "analysis_id": case.get("analysis_id"),
                "source_title": source_title,
                "extracted_words": extracted_words,
                "source_sha256": source_hash,
                "segment_count": len(result.segments),
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            }
        )
        _write_output(
            settings.gemini_model,
            manifest_sha,
            completed,
            complete=False,
        )
        print(f"{case['id']}: generated {len(candidates)} candidates")

    _write_output(
        settings.gemini_model,
        manifest_sha,
        completed,
        complete=True,
    )
    print(f"Wrote complete pool to {OUTPUT}")
    return 0


def _load_case(
    case: dict[str, object],
    store: Store,
    settings: Settings,
) -> tuple[AnalysisResult, str, str | None, int]:
    language = Language(case["source_language"])
    analysis_id = case.get("analysis_id")
    if isinstance(analysis_id, str):
        job = store.get_analysis(analysis_id)
        if job is None or job.result is None:
            raise RuntimeError(
                f"Stored analysis {analysis_id} is missing. Restore the evaluation database."
            )
        if job.result.source_language is not language:
            raise RuntimeError(f"Stored analysis {analysis_id} has the wrong source language.")
        source_text = "\n".join(segment.source_text for segment in job.result.segments)
        return (
            job.result,
            sha256(source_text.encode()).hexdigest(),
            job.result.source_title,
            len(source_text.split()),
        )

    article = extract_article(str(case["url"]), settings)
    segments = segment_article(article.text, language)
    result = AnalysisResult(
        source_language=language,
        source_title=article.title,
        source_url=article.url,
        segments=[
            SegmentResult(
                id=segment.id,
                paragraph_index=segment.paragraph_index,
                sentence_index=segment.sentence_index,
                source_text=segment.text,
                translations=[],
            )
            for segment in segments
        ],
    )
    return (
        result,
        sha256(article.text.encode()).hexdigest(),
        article.title,
        len(article.text.split()),
    )


def _existing_cases(model: str, manifest_sha: str) -> dict[str, dict[str, object]]:
    if not OUTPUT.exists():
        return {}
    data = json.loads(OUTPUT.read_text())
    if (
        data.get("model") != model
        or data.get("manifest_sha256") != manifest_sha
        or data.get("pipeline_version") != PIPELINE_VERSION
    ):
        return {}
    return {case["id"]: case for case in data.get("cases", [])}


def _write_output(
    model: str,
    manifest_sha: str,
    cases: list[dict[str, object]],
    *,
    complete: bool,
    stopped_at: str | None = None,
    error: str | None = None,
) -> None:
    output = {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "updated_at": datetime.now(UTC).isoformat(),
        "model": model,
        "manifest_sha256": manifest_sha,
        "complete": complete,
        "stopped_at": stopped_at,
        "error": error,
        "purpose": (
            "Source-grounded candidate pool for later human selection of 10 claims "
            "per language. This artifact contains no truth or evidence labels."
        ),
        "cases": cases,
    }
    temporary = OUTPUT.with_suffix(f"{OUTPUT.suffix}.tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(OUTPUT)


if __name__ == "__main__":
    raise SystemExit(main())
