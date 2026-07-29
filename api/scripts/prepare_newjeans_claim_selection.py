import argparse
from pathlib import Path

from app.fact_check_evaluation import write_pool_selection_sheet

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
POOL = EVALUATION_DIR / "newjeans-claim-pool.json"
DEFAULT_OUTPUT = EVALUATION_DIR / "newjeans-claim-selection.csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the human selection sheet for the 30-claim evaluation."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing sheet and discard its judgments.",
    )
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} already exists. Move it or pass --force to replace it.")
    with args.output.open("w", newline="") as output:
        write_pool_selection_sheet(POOL, output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
