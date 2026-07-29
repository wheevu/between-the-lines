import json
from pathlib import Path

from app.evidence_evaluation import validate_adjudication

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"


def main() -> int:
    summary = validate_adjudication(
        EVALUATION_DIR / "newjeans-evidence-adjudication.json",
        EVALUATION_DIR / "newjeans-claim-selection.csv",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_system_evaluation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
