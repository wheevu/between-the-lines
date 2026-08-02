import pytest

from app.config import load_settings


def test_embedding_backend_defaults_to_torch(monkeypatch) -> None:
    monkeypatch.delenv("BTL_EMBEDDING_BACKEND", raising=False)

    assert load_settings().embedding_backend == "torch"


def test_embedding_backend_rejects_unknown_runtime(monkeypatch) -> None:
    monkeypatch.setenv("BTL_EMBEDDING_BACKEND", "mystery")

    with pytest.raises(ValueError, match="torch.*openvino"):
        load_settings()


def test_claim_trace_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("BTL_CLAIM_TRACE_ENABLED", raising=False)

    assert load_settings().claim_trace_enabled is False


def test_claim_trace_requires_an_explicit_binary_flag(monkeypatch) -> None:
    monkeypatch.setenv("BTL_CLAIM_TRACE_ENABLED", "1")
    assert load_settings().claim_trace_enabled is True

    monkeypatch.setenv("BTL_CLAIM_TRACE_ENABLED", "true")
    with pytest.raises(ValueError, match="BTL_CLAIM_TRACE_ENABLED.*0.*1"):
        load_settings()
