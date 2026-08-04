import argparse
import json
from pathlib import Path

from app.evidence_evaluation import merge_adjudication

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
DEFAULT_PACKETS = EVALUATION_DIR / "adjudication-packets"
DEFAULT_TEMPLATE = EVALUATION_DIR / "newjeans-evidence-adjudication.json"
DEFAULT_OUTPUT = EVALUATION_DIR / "newjeans-evidence-adjudication.json"
DEFAULT_SELECTION = EVALUATION_DIR / "newjeans-claim-selection.csv"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge the two completed adjudicator workbooks into the gold file."
    )
    parser.add_argument("--packet-a", type=Path, default=DEFAULT_PACKETS / "reviewer-a.json")
    parser.add_argument("--packet-b", type=Path, default=DEFAULT_PACKETS / "reviewer-b.json")
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="The freshly prepared template; hash-bound fields are checked against it.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Canonical gold file; refuses to overwrite one that is already ready.",
    )
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    args = parser.parse_args()
    missing = [
        path
        for path in (args.packet_a, args.packet_b, args.template, args.selection)
        if not path.exists()
    ]
    if missing:
        raise SystemExit("Missing files: " + ", ".join(str(path) for path in missing))

    try:
        result = merge_adjudication(
            args.packet_a,
            args.packet_b,
            args.template,
            args.output,
            args.selection,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    summary = result["summary"]
    report = {
        "output": result["output"],
        "ready_claims": summary["ready_claims"],
        "disagreements": result["disagreements"],
        "ready_for_system_evaluation": summary["ready_for_system_evaluation"],
        "claim_issues": summary["claim_issues"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if summary["claim_issues"]:
        print("\nResolve the listed claim issues (or disagreements) before the frozen run.")
        return 1
    print("\nGold adjudication is structurally complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
