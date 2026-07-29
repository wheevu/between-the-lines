import argparse
import json
from pathlib import Path

from app.evidence_evaluation import prepare_adjudication

EVALUATION_DIR = Path(__file__).parents[1] / "evaluation"
DEFAULT_OUTPUT = EVALUATION_DIR / "newjeans-evidence-adjudication.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare gold-evidence adjudication for the frozen 30 claims."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"{args.output} already exists. Move it before preparing again.")
    try:
        output = prepare_adjudication(
            EVALUATION_DIR / "newjeans-claim-pool.json",
            EVALUATION_DIR / "newjeans-claim-selection.csv",
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
