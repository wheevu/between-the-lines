"""Lazy-loading multilingual E5 embedder with idle unload and graceful fallback."""

from __future__ import annotations

import gc
import importlib.util
import time
from collections.abc import Sequence
from os import environ
from pathlib import Path
from threading import Lock

MODEL_ID = "intfloat/multilingual-e5-small"
DEFAULT_IDLE_SECONDS = 300.0


class EmbeddingUnavailableError(RuntimeError):
    """Raised when local E5 embeddings cannot be loaded in the current environment."""


class LocalEmbedder:
    """Thread-safe lazy loader for intfloat/multilingual-e5-small with idle unload."""

    def __init__(
        self,
        *,
        backend: str | None = None,
        idle_seconds: float | None = None,
        offline_only: bool | None = None,
        allow_download: bool | None = None,
    ) -> None:
        resolved_backend = (backend or environ.get("BTL_EMBEDDING_BACKEND", "torch")).lower()
        if resolved_backend not in {"torch", "openvino"}:
            raise ValueError("BTL_EMBEDDING_BACKEND must be 'torch' or 'openvino'.")
        self.backend = resolved_backend
        self.idle_seconds = (
            idle_seconds
            if idle_seconds is not None
            else float(environ.get("BTL_EMBEDDING_IDLE_SECONDS", str(DEFAULT_IDLE_SECONDS)))
        )
        self.offline_only = (
            offline_only
            if offline_only is not None
            else environ.get("BTL_OFFLINE_ONLY", "0") == "1"
        )
        self.allow_download = (
            allow_download
            if allow_download is not None
            else environ.get("BTL_ALLOW_MODEL_DOWNLOAD", "0") == "1"
        )
        self._lock = Lock()
        self._model = None
        self._last_used: float | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def is_cached(self) -> bool:
        hf_hub = Path(environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
        return (hf_hub / "models--intfloat--multilingual-e5-small").exists()

    def status(self) -> dict[str, object]:
        """Inspect package and Hugging Face cache status without loading PyTorch."""
        has_st = importlib.util.find_spec("sentence_transformers") is not None
        has_torch = importlib.util.find_spec("torch") is not None
        return {
            "model_id": MODEL_ID,
            "backend": self.backend,
            "sentence_transformers_installed": has_st,
            "torch_installed": has_torch,
            "model_cached": self.is_cached(),
            "loaded": self.is_loaded,
            "offline_only": self.offline_only,
            "allow_download": self.allow_download,
            "idle_seconds": self.idle_seconds,
        }

    def warmup(self) -> dict[str, object]:
        """Download (if needed) and verify local embedding model readiness."""
        prev_allow = self.allow_download
        self.allow_download = True
        try:
            with self._lock:
                self._ensure_loaded()
        finally:
            self.allow_download = prev_allow
        return self.status()

    def similarities(self, left: Sequence[str], right: Sequence[str]) -> list[float]:
        """Compute E5 query-to-passage cosine similarities for aligned pairs."""
        if len(left) != len(right):
            raise ValueError("Similarity inputs must have equal lengths.")
        if not left:
            return []
        with self._lock:
            self._ensure_loaded()
            assert self._model is not None
            src = self._model.encode(
                [f"query: {text}" for text in left],
                normalize_embeddings=True,
            )
            dst = self._model.encode(
                [f"passage: {text}" for text in right],
                normalize_embeddings=True,
            )
            self._last_used = time.monotonic()
            return [float(a @ b) for a, b in zip(src, dst, strict=True)]

    def maybe_unload_idle(self, *, now: float | None = None) -> bool:
        """Unload cached weights after `idle_seconds` of inactivity."""
        if self.idle_seconds <= 0:
            return False
        with self._lock:
            if self._model is None or self._last_used is None:
                return False
            current = time.monotonic() if now is None else now
            if current - self._last_used < self.idle_seconds:
                return False
            self._model = None
            self._last_used = None
        gc.collect()
        return True

    def unload(self) -> None:
        """Explicitly release loaded model weights."""
        with self._lock:
            self._model = None
            self._last_used = None
        gc.collect()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        if importlib.util.find_spec("sentence_transformers") is None:
            raise EmbeddingUnavailableError(
                "sentence-transformers is not installed; using lexical fallback."
            )
        if not self.is_cached() and (self.offline_only or not self.allow_download):
            raise EmbeddingUnavailableError(
                f"{MODEL_ID} is not cached locally; run './bin/btl warmup' first or use lexical."
            )
        from sentence_transformers import SentenceTransformer

        model_kwargs: dict[str, object] = {}
        if self.backend == "openvino":
            model_kwargs["model_kwargs"] = {"export": True}
        if self.offline_only:
            model_kwargs["local_files_only"] = True
        try:
            self._model = SentenceTransformer(
                MODEL_ID,
                backend=self.backend,
                device="cpu" if self.backend == "openvino" else None,
                **model_kwargs,
            )
            self._last_used = time.monotonic()
        except Exception as error:
            raise EmbeddingUnavailableError(
                f"Could not load {MODEL_ID}: {error}"
            ) from error
