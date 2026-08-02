from dataclasses import dataclass
from os import environ
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    database_path: Path
    fact_check_api_key: str | None = None
    embedding_backend: str = "torch"
    max_article_words: int = 2_500
    max_download_bytes: int = 2 * 1024 * 1024
    claim_trace_enabled: bool = False


def load_settings() -> Settings:
    data_dir = Path(environ.get("BTL_DATA_DIR", Path(__file__).parents[1] / "data"))
    embedding_backend = environ.get("BTL_EMBEDDING_BACKEND", "torch").lower()
    if embedding_backend not in {"torch", "openvino"}:
        raise ValueError("BTL_EMBEDDING_BACKEND must be 'torch' or 'openvino'.")
    claim_trace_enabled = environ.get("BTL_CLAIM_TRACE_ENABLED", "0")
    if claim_trace_enabled not in {"0", "1"}:
        raise ValueError("BTL_CLAIM_TRACE_ENABLED must be '0' or '1'.")
    return Settings(
        gemini_api_key=environ.get("GOOGLE_GENERATIVE_AI_API_KEY"),
        gemini_model=environ.get("BTL_GEMINI_MODEL", "gemini-3.1-flash-lite"),
        database_path=data_dir / "between-the-lines.sqlite3",
        fact_check_api_key=environ.get("GOOGLE_FACT_CHECK_API_KEY"),
        embedding_backend=embedding_backend,
        claim_trace_enabled=claim_trace_enabled == "1",
    )
