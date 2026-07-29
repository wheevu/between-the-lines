import json
from pathlib import Path

from app.analyzer import Analyzer
from app.config import load_settings
from app.gemini import GeminiTranslator
from app.models import AnalysisCreate, Language
from app.store import Store

FIXTURE = Path(__file__).parents[1] / "evaluation" / "risk-rich-excerpts.json"
OUTPUT = Path(__file__).parents[1] / "evaluation" / "risk-rich-analysis-links.json"


def main() -> None:
    settings = load_settings()
    store = Store(settings.database_path)
    store.initialize()
    analyzer = Analyzer(
        settings=settings,
        store=store,
        gemini=GeminiTranslator(settings.gemini_api_key, settings.gemini_model),
    )
    data = json.loads(FIXTURE.read_text())
    results = []

    for case in data["cases"]:
        job = store.create_analysis()
        analyzer.run(
            job.id,
            AnalysisCreate(
                source_language=Language(case["source_language"]),
                text=case["text"],
            ),
        )
        completed = store.get_analysis(job.id)
        if completed is None or completed.result is None:
            raise RuntimeError(
                f"{case['id']} failed: {completed.error if completed else 'missing job'}"
            )
        finding_count = sum(
            len(translation.flags)
            for segment in completed.result.segments
            for translation in segment.translations
        )
        meaning_risk_count = sum(
            flag.kind.value == "meaning-risk"
            for segment in completed.result.segments
            for translation in segment.translations
            for flag in translation.flags
        )
        reviewer_role = (
            "author" if case["source_language"] == Language.KOREAN.value else "independent"
        )
        results.append(
            {
                "id": case["id"],
                "analysis_id": job.id,
                "source_language": case["source_language"],
                "finding_count": finding_count,
                "meaning_risk_count": meaning_risk_count,
                "review_url": (
                    f"http://127.0.0.1:5173/?analysis={job.id}&reviewer={reviewer_role}"
                ),
            }
        )
        print(
            f"{case['id']}: {finding_count} findings, {meaning_risk_count} meaning risks — {job.id}"
        )

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
