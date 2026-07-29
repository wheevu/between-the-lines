import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.config import load_settings
from app.local_models import LocalModels
from app.recall_evaluation import (
    corpus_sha256,
    run_holdout_retrieval_diagnostics,
    validate_publisher_holdout,
)

API_DIR = Path(__file__).parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the publisher-held-out retrieval check.")
    parser.add_argument(
        "--output",
        type=Path,
        default=API_DIR / "evaluation" / "claim-trace-publisher-holdout-result-v1.json",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("The holdout result already exists; use a new versioned path.")
    core_path = API_DIR / "evaluation" / "claim-trace-corpus.json"
    robustness_path = API_DIR / "evaluation" / "claim-trace-robustness-corpus.json"
    holdout_path = API_DIR / "evaluation" / "claim-trace-publisher-holdout-v1.json"
    core = json.loads(core_path.read_text())
    robustness = json.loads(robustness_path.read_text())
    holdout = json.loads(holdout_path.read_text())
    validation = validate_publisher_holdout(
        holdout,
        robustness,
        core,
        corpus_sha256(robustness_path),
    )
    if not validation["ready_for_retrieval_diagnostics"]:
        raise ValueError("The publisher holdout is incomplete or no longer frozen.")
    settings = load_settings()
    result = run_holdout_retrieval_diagnostics(
        core,
        robustness,
        holdout,
        settings,
        LocalModels(settings.embedding_backend),
    )
    result.update(
        {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "corpus_sha256": corpus_sha256(robustness_path),
            "holdout_sha256": sha256(holdout_path.read_bytes()).hexdigest(),
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
