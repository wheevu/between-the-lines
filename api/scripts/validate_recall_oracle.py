import json
from pathlib import Path

from app.recall_evaluation import corpus_sha256, validate_recall_oracle

API_DIR = Path(__file__).parents[1]


def main() -> int:
    manifest_path = API_DIR / "evaluation" / "claim-trace-corpus.json"
    oracle_path = API_DIR / "evaluation" / "claim-trace-recall-oracle-v1.json"
    manifest = json.loads(manifest_path.read_text())
    oracle = json.loads(oracle_path.read_text())
    summary = validate_recall_oracle(oracle, manifest, corpus_sha256(manifest_path))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_diagnostics"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
