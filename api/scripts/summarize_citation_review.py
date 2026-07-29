import json
from pathlib import Path

from app.citation_evaluation import summarize_citation_review

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


def main() -> int:
    try:
        summary = summarize_citation_review(
            EVALUATION_DIR / "newjeans-evidence-adjudication.json",
            EVALUATION_DIR / "newjeans-claim-selection.csv",
            EVALUATION_DIR / "newjeans-system-results.json",
            EVALUATION_DIR / "newjeans-citation-review.csv",
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"Citation review cannot be summarized: {error}") from error
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["citation_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
