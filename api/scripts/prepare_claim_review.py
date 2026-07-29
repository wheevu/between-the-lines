import argparse
from pathlib import Path

from app.claim_evaluation import write_claim_review_sheet

CANDIDATES = Path(__file__).parents[1] / "evaluation" / "cross-domain-claim-candidates.json"
DEFAULT_OUTPUT = Path(__file__).parents[1] / "evaluation" / "cross-domain-claim-review.csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the bilingual review sheet for frozen claim candidates."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing sheet. This discards any judgments in that file.",
    )
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} already exists. Move it or pass --force to replace it.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as output:
        write_claim_review_sheet(CANDIDATES, output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
