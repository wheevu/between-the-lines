import argparse
import json
from hashlib import sha256
from pathlib import Path

from app.config import load_settings
from app.evaluation_summary import summarize_database
from app.evidence_evaluation import validate_adjudication
from app.evidence_retrieval import FactCheckToolsProvider, GoogleSearchProvider
from app.evidence_synthesis import EvidenceClassifier
from app.fact_check_evaluation import summarize_pool_selection
from app.fact_checker import FactChecker
from app.local_models import LocalModels
from app.query_generator import QueryGenerator
from app.store import Store
from app.system_run import load_frozen_claims, run_frozen_claims

API_DIR = Path(__file__).parents[1]
EVALUATION_DIR = API_DIR / "evaluation"
DEFAULT_OUTPUT = EVALUATION_DIR / "newjeans-system-results.json"
PIPELINE_FILES = [
    API_DIR / "app" / name
    for name in (
        "evidence_ranker.py",
        "evidence_retrieval.py",
        "evidence_synthesis.py",
        "fact_checker.py",
        "local_models.py",
        "models.py",
        "query_generator.py",
        "system_run.py",
    )
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the gated frozen 30-claim evidence evaluation."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--limit",
        type=_claim_batch_size,
        required=True,
        help=(
            "Process 1–5 new claims, then checkpoint. Choose the batch only after "
            "checking the configured account's free quota."
        ),
    )
    args = parser.parse_args()
    settings = load_settings()
    paths = {
        "corpus": EVALUATION_DIR / "newjeans-corpus.json",
        "pool": EVALUATION_DIR / "newjeans-claim-pool.json",
        "selection": EVALUATION_DIR / "newjeans-claim-selection.csv",
        "adjudication": EVALUATION_DIR / "newjeans-evidence-adjudication.json",
    }
    try:
        if not settings.database_path.exists():
            raise ValueError("The translation-review database is missing.")
        translation = summarize_database(settings.database_path)
        if not translation["ready_for_evidence_layer_decision"]:
            raise ValueError(
                "Translation review is not ready: " + " ".join(translation["blockers"])
            )
        selection = summarize_pool_selection(paths["pool"], paths["selection"])
        if not selection["ready_for_evidence_adjudication"]:
            raise ValueError(
                "The balanced claim selection is not ready: " + " ".join(selection["blockers"])
            )
        adjudication = validate_adjudication(paths["adjudication"], paths["selection"])
        if not adjudication["ready_for_system_evaluation"]:
            raise ValueError(
                "Gold evidence adjudication is not ready: " + " ".join(adjudication["blockers"])
            )
        if not settings.gemini_api_key:
            raise ValueError(
                "GOOGLE_GENERATIVE_AI_API_KEY is required for query, discovery, and stance calls."
            )
        claims = load_frozen_claims(
            paths["adjudication"],
            paths["pool"],
            paths["corpus"],
        )
        checker = FactChecker(
            settings=settings,
            store=Store(settings.database_path),
            query_generator=QueryGenerator(settings.gemini_api_key, settings.gemini_model),
            fact_check_provider=FactCheckToolsProvider(settings.fact_check_api_key),
            search_provider=GoogleSearchProvider(
                settings.gemini_api_key,
                settings.gemini_model,
            ),
            local_models=LocalModels(settings.embedding_backend),
            classifier=EvidenceClassifier(
                settings.gemini_api_key,
                settings.gemini_model,
            ),
        )
        state = run_frozen_claims(
            checker,
            claims,
            args.output,
            identity={
                "adjudication_sha256": _sha256(paths["adjudication"]),
                "selection_sha256": _sha256(paths["selection"]),
                "pool_sha256": _sha256(paths["pool"]),
                "corpus_sha256": _sha256(paths["corpus"]),
                "pipeline_sha256": _pipeline_sha256(),
                "gemini_model": settings.gemini_model,
                "embedding_backend": settings.embedding_backend,
                "fact_check_tools_configured": bool(settings.fact_check_api_key),
            },
            max_new_claims=args.limit,
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"System evaluation cannot run: {error}") from error

    summary = {
        "output": str(args.output),
        "complete": state["complete"],
        "claims": len(state["claims"]),
        "stopped_at": state["stopped_at"],
        "pause_reason": state["pause_reason"],
        "error": state["error"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if state["complete"] else 2


def _pipeline_sha256() -> str:
    digest = sha256()
    for path in PIPELINE_FILES:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _claim_batch_size(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 5:
        raise argparse.ArgumentTypeError("must be between 1 and 5")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
