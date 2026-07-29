import argparse
import sys
from pathlib import Path

from app.config import load_settings
from app.feedback_export import write_feedback


def main() -> None:
    parser = argparse.ArgumentParser(description="Export translation review feedback.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        write_feedback(load_settings().database_path, sys.stdout)
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as output:
        write_feedback(load_settings().database_path, output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
