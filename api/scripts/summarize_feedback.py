import argparse
import json
from pathlib import Path

from app.config import load_settings
from app.evaluation_summary import summarize_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize translation review feedback.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = summarize_database(load_settings().database_path)
    rendered = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n")
        print(f"Wrote {args.output}")
        return
    print(rendered)


if __name__ == "__main__":
    main()
