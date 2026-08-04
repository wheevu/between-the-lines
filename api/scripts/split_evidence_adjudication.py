import argparse
import json
from pathlib import Path

from app.evidence_evaluation import split_adjudication

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
DEFAULT_TEMPLATE = EVALUATION_DIR / "newjeans-evidence-adjudication.json"
DEFAULT_PACKETS = EVALUATION_DIR / "adjudication-packets"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create one gold-evidence workbook per independent adjudicator."
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Freshly prepared adjudication file with empty gold blocks.",
    )
    parser.add_argument(
        "--packets",
        type=Path,
        default=DEFAULT_PACKETS,
        help="Directory that receives reviewer-a.json and reviewer-b.json.",
    )
    args = parser.parse_args()
    if not args.template.exists():
        raise SystemExit(
            f"{args.template} does not exist. Run prepare_evidence_adjudication.py first."
        )
    try:
        result = split_adjudication(args.template, args.packets)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(
        json.dumps(
            {
                "claims": result["claims"],
                "packets": result["packets"],
            },
            indent=2,
        )
    )
    print(
        "\nEach reviewer completes their own workbook, then run "
        "scripts/merge_evidence_adjudication.py."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
