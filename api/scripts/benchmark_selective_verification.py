import argparse
import json
import platform
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from app.ambiguity import needs_local_verification
from app.article import extract_article
from app.config import load_settings
from app.local_models import LocalModels
from app.models import Language
from app.segmentation import segment_article

MANIFEST = Path(__file__).parents[1] / "evaluation" / "claim-trace-corpus.json"
DEFAULT_OUTPUT = Path(__file__).parents[1] / "evaluation" / "selective-verification-m1.json"
TARGET = {
    Language.ENGLISH: Language.VIETNAMESE,
    Language.VIETNAMESE: Language.KOREAN,
    Language.KOREAN: Language.ENGLISH,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare full NLLB checking with risk-routed NLLB checking."
    )
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def balanced_articles(limit: int) -> list[dict[str, str]]:
    if limit < 1:
        raise ValueError("--limit must be at least 1.")
    manifest = json.loads(MANIFEST.read_text())
    by_language: dict[Language, list[dict[str, str]]] = {language: [] for language in Language}
    for event in manifest["events"]:
        for article in event["articles"]:
            by_language[Language(article["source_language"])].append(article)
    selected = []
    while len(selected) < limit and any(by_language.values()):
        for language in Language:
            if by_language[language] and len(selected) < limit:
                selected.append(by_language[language].pop(0))
    return selected


def benchmark(limit: int) -> dict[str, object]:
    settings = load_settings()
    models = LocalModels()
    cases = []
    failures = []
    for article in balanced_articles(limit):
        source = Language(article["source_language"])
        target = TARGET[source]
        try:
            extracted = extract_article(article["url"], settings)
        except Exception as error:
            failures.append({"article_id": article["id"], "reason": str(error)})
            continue
        segments = segment_article(extracted.text, source)
        source_texts = [segment.text for segment in segments]
        selected_indexes = [
            index
            for index, text in enumerate(source_texts)
            if needs_local_verification(
                text,
                source,
                segment_index=index,
                has_model_notes=False,
            )
        ]
        selected_texts = [source_texts[index] for index in selected_indexes]

        warmup_started = perf_counter()
        models.translate([source_texts[0]], source, target)
        warmup_seconds = perf_counter() - warmup_started

        selected_started = perf_counter()
        models.translate(selected_texts, source, target)
        selected_seconds = perf_counter() - selected_started

        full_started = perf_counter()
        models.translate(source_texts, source, target)
        full_seconds = perf_counter() - full_started
        cases.append(
            {
                "article_id": article["id"],
                "source_language": source.value,
                "target_language": target.value,
                "segments": len(source_texts),
                "locally_checked_segments": len(selected_texts),
                "local_model_segment_share": round(len(selected_texts) / len(source_texts), 4),
                "direction_warmup_seconds_excluded": round(warmup_seconds, 3),
                "selective_seconds": round(selected_seconds, 3),
                "full_seconds": round(full_seconds, 3),
            }
        )

    selected_total = sum(case["selective_seconds"] for case in cases)
    full_total = sum(case["full_seconds"] for case in cases)
    segments = sum(case["segments"] for case in cases)
    checked = sum(case["locally_checked_segments"] for case in cases)
    return {
        "purpose": "Measure only the local NLLB stage; Gemini and extraction are excluded.",
        "manifest_sha256": sha256(MANIFEST.read_bytes()).hexdigest(),
        "machine": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "warmup_excluded": True,
        "execution_order": "selective then full for each article",
        "cases": cases,
        "failures": failures,
        "summary": {
            "articles": len(cases),
            "segments": segments,
            "locally_checked_segments": checked,
            "local_model_segment_share": round(checked / segments, 4) if segments else None,
            "selective_seconds": round(selected_total, 3),
            "full_seconds": round(full_total, 3),
            "speedup": round(full_total / selected_total, 2) if selected_total else None,
        },
        "limitations": [
            "Gemini notes are unavailable before a live translation, so this benchmark "
            "routes on source-text risk markers only.",
            "The per-article execution order can favor the selective pass through "
            "transient caching.",
            "This Apple Silicon result cannot support an Intel performance claim.",
        ],
    }


def main() -> None:
    args = parse_args()
    result = benchmark(args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    if result["failures"]:
        print(f"Retrieval failures: {len(result['failures'])}")


if __name__ == "__main__":
    main()
