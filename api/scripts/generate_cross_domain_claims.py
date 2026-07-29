import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.article import extract_article
from app.claim_extractor import ClaimExtractor
from app.config import load_settings
from app.models import AnalysisResult, Language, SegmentResult
from app.segmentation import segment_article
from app.store import Store

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
MANIFEST = EVALUATION_DIR / "cross-domain-smoke.json"
DEFAULT_OUTPUT = EVALUATION_DIR / "cross-domain-claim-candidates.json"
PIPELINE_VERSION = 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate source-grounded claim candidates for the general-news smoke set."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    settings = load_settings()
    manifest = json.loads(MANIFEST.read_text())
    extractor = ClaimExtractor(
        Store(settings.database_path),
        settings.gemini_api_key,
        settings.gemini_model,
    )
    cases = []
    for case in manifest["cases"]:
        article = extract_article(case["url"], settings)
        language = Language(case["source_language"])
        source_segments = segment_article(article.text, language)
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
                for segment in source_segments
            ],
        )
        candidates = extractor.extract(result)
        cases.append(
            {
                "id": case["id"],
                "source_language": language.value,
                "topic": case["topic"],
                "published": case["published"],
                "url": case["url"],
                "source_title": article.title,
                "extracted_words": len(article.text.split()),
                "source_sha256": sha256(article.text.encode()).hexdigest(),
                "segment_count": len(source_segments),
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            }
        )
        print(f"{case['id']}: {len(candidates)} grounded candidates")

    output = {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": settings.gemini_model,
        "manifest_sha256": sha256(MANIFEST.read_bytes()).hexdigest(),
        "purpose": (
            "Freeze general-news claim candidates before human centrality and "
            "checkability review. This artifact does not contain truth labels."
        ),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
