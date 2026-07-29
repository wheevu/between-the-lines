import json
from pathlib import Path

from app.system_evaluation import summarize_system_run

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


def main() -> int:
    summary = summarize_system_run(
        EVALUATION_DIR / "newjeans-evidence-adjudication.json",
        EVALUATION_DIR / "newjeans-claim-selection.csv",
        EVALUATION_DIR / "newjeans-system-results.json",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_human_citation_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
