import argparse
import json
import platform
import statistics
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
DEFAULT_OUTPUT = Path(__file__).parents[1] / "evaluation" / "selective-embedding-m1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark full versus risk-routed multilingual E5 comparison."
    )
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--runs", type=int, default=5)
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


def timed_similarity(
    models: LocalModels,
    left: list[str],
    right: list[str],
    runs: int,
) -> list[float]:
    timings = []
    for _ in range(runs):
        started = perf_counter()
        models.similarities(left, right)
        timings.append((perf_counter() - started) * 1_000)
    return timings


def benchmark(limit: int, runs: int) -> dict[str, object]:
    if runs < 1:
        raise ValueError("--runs must be at least 1.")
    settings = load_settings()
    models = LocalModels(settings.embedding_backend)
    models.similarities(["Warm up."], ["Warm up."])
    cases = []
    failures = []
    for article in balanced_articles(limit):
        source = Language(article["source_language"])
        try:
            extracted = extract_article(article["url"], settings)
        except Exception as error:
            failures.append({"article_id": article["id"], "reason": str(error)})
            continue
        segments = segment_article(extracted.text, source)
        texts = [segment.text for segment in segments]
        selected_indexes = [
            index
            for index, text in enumerate(texts)
            if needs_local_verification(
                text,
                source,
                segment_index=index,
                has_model_notes=False,
            )
        ]
        selected_texts = [texts[index] for index in selected_indexes]
        selective_timings = timed_similarity(models, selected_texts, selected_texts, runs)
        full_timings = timed_similarity(models, texts, texts, runs)
        cases.append(
            {
                "article_id": article["id"],
                "source_language": source.value,
                "segments": len(texts),
                "locally_checked_segments": len(selected_texts),
                "local_model_segment_share": round(len(selected_texts) / len(texts), 4),
                "selective_median_ms": round(statistics.median(selective_timings), 2),
                "full_median_ms": round(statistics.median(full_timings), 2),
            }
        )

    segments = sum(case["segments"] for case in cases)
    checked = sum(case["locally_checked_segments"] for case in cases)
    selective_ms = sum(case["selective_median_ms"] for case in cases)
    full_ms = sum(case["full_median_ms"] for case in cases)
    return {
        "purpose": "Measure the local E5 stage independently of Gemini and extraction.",
        "manifest_sha256": sha256(MANIFEST.read_bytes()).hexdigest(),
        "embedding_backend": settings.embedding_backend,
        "machine": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "warmup_excluded": True,
        "runs_per_article": runs,
        "cases": cases,
        "failures": failures,
        "summary": {
            "articles": len(cases),
            "segments": segments,
            "locally_checked_segments": checked,
            "local_model_segment_share": round(checked / segments, 4) if segments else None,
            "selective_median_sum_ms": round(selective_ms, 2),
            "full_median_sum_ms": round(full_ms, 2),
            "speedup": round(full_ms / selective_ms, 2) if selective_ms else None,
        },
        "limitations": [
            "Identical text pairs isolate runtime; they do not measure cross-language quality.",
            "Gemini notes can route additional passages in the live pipeline.",
            "This Apple Silicon result cannot support an Intel performance claim.",
        ],
    }


def main() -> None:
    args = parse_args()
    result = benchmark(args.limit, args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    if result["failures"]:
        print(f"Retrieval failures: {len(result['failures'])}")


if __name__ == "__main__":
    main()
