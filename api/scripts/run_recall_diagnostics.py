import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.config import load_settings
from app.local_models import LocalModels
from app.recall_evaluation import (
    corpus_sha256,
    run_recall_diagnostics,
    validate_recall_oracle,
)

API_DIR = Path(__file__).parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Localize failures in frozen Claim Trace recall.")
    parser.add_argument(
        "--output",
        type=Path,
        default=API_DIR / "evaluation" / "claim-trace-recall-diagnostic-v1.json",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("The diagnostic output already exists; use a new versioned path.")

    manifest_path = API_DIR / "evaluation" / "claim-trace-corpus.json"
    oracle_path = API_DIR / "evaluation" / "claim-trace-recall-oracle-v1.json"
    baseline_path = API_DIR / "evaluation" / "claim-trace-closed-set-full.json"
    manifest = json.loads(manifest_path.read_text())
    oracle = json.loads(oracle_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    oracle_summary = validate_recall_oracle(
        oracle,
        manifest,
        corpus_sha256(manifest_path),
    )
    if not oracle_summary["ready_for_diagnostics"]:
        raise ValueError("The recall oracle is incomplete or no longer matches the corpus.")
    if baseline.get("corpus_sha256") != corpus_sha256(manifest_path):
        raise ValueError("The historical baseline does not match the frozen corpus.")

    settings = load_settings()
    local_models = LocalModels(settings.embedding_backend)
    result = run_recall_diagnostics(manifest, oracle, baseline, settings, local_models)
    result.update(
        {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "corpus_sha256": corpus_sha256(manifest_path),
            "oracle_sha256": sha256(oracle_path.read_bytes()).hexdigest(),
            "baseline_sha256": sha256(baseline_path.read_bytes()).hexdigest(),
            "embedding_backend": settings.embedding_backend,
            "stores_article_text": False,
        }
    )
    temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
