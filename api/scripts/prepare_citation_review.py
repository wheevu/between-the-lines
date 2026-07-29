import argparse
from io import StringIO
from pathlib import Path

from app.citation_evaluation import write_citation_review_sheet

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
DEFAULT_OUTPUT = EVALUATION_DIR / "newjeans-citation-review.csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare human review of citations in the frozen system run."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"{args.output} already exists. Move it before preparing again.")
    try:
        prepared = StringIO()
        write_citation_review_sheet(
            EVALUATION_DIR / "newjeans-evidence-adjudication.json",
            EVALUATION_DIR / "newjeans-claim-selection.csv",
            EVALUATION_DIR / "newjeans-system-results.json",
            prepared,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", newline="") as output:
            output.write(prepared.getvalue())
    except (OSError, ValueError) as error:
        raise SystemExit(f"Citation review cannot be prepared: {error}") from error
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
