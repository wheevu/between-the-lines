import json
from pathlib import Path

from app.fact_check_evaluation import summarize_pool_selection

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


def main() -> None:
    summary = summarize_pool_selection(
        EVALUATION_DIR / "newjeans-claim-pool.json",
        EVALUATION_DIR / "newjeans-claim-selection.csv",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
