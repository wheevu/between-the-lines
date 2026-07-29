import pytest

from app.config import load_settings


def test_embedding_backend_defaults_to_torch(monkeypatch) -> None:
    monkeypatch.delenv("BTL_EMBEDDING_BACKEND", raising=False)

    assert load_settings().embedding_backend == "torch"


def test_embedding_backend_rejects_unknown_runtime(monkeypatch) -> None:
    monkeypatch.setenv("BTL_EMBEDDING_BACKEND", "mystery")

    with pytest.raises(ValueError, match="torch.*openvino"):
        load_settings()
