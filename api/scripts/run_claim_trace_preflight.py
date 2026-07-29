import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.claim_trace_benchmark import run_preflight
from app.config import load_settings

API_DIR = Path(__file__).parents[1]
DEFAULT_MANIFEST = API_DIR / "evaluation" / "claim-trace-corpus.json"
DEFAULT_OUTPUT = API_DIR / "evaluation" / "claim-trace-preflight-2026-07-24.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check extraction readiness for the frozen Claim Trace corpus."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=_positive_int, default=6)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    report = run_preflight(
        manifest,
        load_settings(),
        workers=args.workers,
    )
    report["generated_at"] = datetime.now(UTC).isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["ready"] == report["summary"]["total"] else 2


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
