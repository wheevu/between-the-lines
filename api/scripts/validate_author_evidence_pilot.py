import json
from pathlib import Path

from app.author_pilot_evaluation import validate_author_pilot

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


def main() -> int:
    summary = validate_author_pilot(
        EVALUATION_DIR / "newjeans-author-evidence-pilot.json",
        EVALUATION_DIR / "newjeans-claim-selection.csv",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_author_pilot"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
