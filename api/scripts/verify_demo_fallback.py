import argparse
import json
import sys
from pathlib import Path

API_DIR = Path(__file__).parents[1]
# Make `app` importable when run as a plain script (not via -m).
sys.path.insert(0, str(API_DIR))

from app.demo_fallback import verify_demo_fallback  # noqa: E402

DEFAULT_DATABASE = API_DIR / "data" / "demo-fallback" / "between-the-lines.sqlite3"
DEFAULT_GUIDE = API_DIR / "evaluation" / "reviewer-guide.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the read-only, network-free recording fallback."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--reviewer-guide", type=Path, default=DEFAULT_GUIDE)
    args = parser.parse_args()

    summary = verify_demo_fallback(args.database, args.reviewer_guide)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_translation_recording"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
