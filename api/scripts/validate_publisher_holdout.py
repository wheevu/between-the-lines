import json
from pathlib import Path

from app.recall_evaluation import corpus_sha256, validate_publisher_holdout

API_DIR = Path(__file__).parents[1]


def main() -> int:
    core_path = API_DIR / "evaluation" / "claim-trace-corpus.json"
    robustness_path = API_DIR / "evaluation" / "claim-trace-robustness-corpus.json"
    holdout_path = API_DIR / "evaluation" / "claim-trace-publisher-holdout-v1.json"
    summary = validate_publisher_holdout(
        json.loads(holdout_path.read_text()),
        json.loads(robustness_path.read_text()),
        json.loads(core_path.read_text()),
        corpus_sha256(robustness_path),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_retrieval_diagnostics"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
