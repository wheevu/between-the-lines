import json
from pathlib import Path

from app.claim_evaluation import summarize_claim_reviews

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


def main() -> None:
    summary = summarize_claim_reviews(
        EVALUATION_DIR / "cross-domain-claim-candidates.json",
        EVALUATION_DIR / "cross-domain-claim-review.csv",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
