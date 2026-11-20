"""Tests for cross-script origin clustering and multilingual passage ranking."""

from __future__ import annotations

from btl.lineage import cluster_origins
from btl.ranker import extract_and_rank
from btl.types import DocumentInput, OriginInputItem


class FakeEmbedder:
    def similarities(self, left: list[str], right: list[str]) -> list[float]:
        scores: list[float] = []
        for lval, rval in zip(left, right, strict=True):
            if "CustomOrg" in lval and "커스텀기관" in rval:
                scores.append(0.97)
            elif "budget" in lval.lower() and "예산" in rval:
                scores.append(0.92)
            else:
                scores.append(0.25)
        return scores


def test_cluster_origins_collapses_cross_script_wires_acronyms_and_dupes() -> None:
    items = [
        OriginInputItem(
            id="s1",
            url="https://en.example.org/a",
            publisher="English Daily",
            credited_origin="Reuters",
            language="en",
            excerpt="Global temperatures hit a record high in 2026.",
        ),
        OriginInputItem(
            id="s2",
            url="https://kr.example.org/b",
            publisher="Seoul Times",
            credited_origin="로이터",
            language="ko",
            excerpt="로이터 보도에 따르면 2026년 세계 기온이 최고치를 기록했다.",
        ),
        OriginInputItem(
            id="s3",
            url="https://wmo-en.example.org/c",
            publisher="Climate Desk",
            credited_origin="World Meteorological Organization",
            language="en",
            excerpt="WMO annual briefing data.",
        ),
        OriginInputItem(
            id="s4",
            url="https://wmo-ko.example.org/d",
            publisher="Hankook Wire",
            credited_origin="세계기상기구(WMO)",
            language="ko",
            excerpt="기상 관측 보고서.",
        ),
        OriginInputItem(
            id="s5",
            url="https://vn.example.org/e",
            publisher="VnExpress",
            credited_origin="VnExpress",
            language="vi",
            excerpt="Báo cáo độc lập tại Hà Nội.",
        ),
    ]
    res = cluster_origins(items)
    assert res.source_count == 5
    assert res.independent_lineage_count == 3
    assert res.syndication_collapsed == 2
    assert res.embeddings_used is False
    member_sets = [set(c.member_ids) for c in res.clusters]
    assert {"s1", "s2"} in member_sets
    assert {"s3", "s4"} in member_sets
    assert {"s5"} in member_sets


def test_cluster_origins_uses_optional_embedder_without_requiring_it() -> None:
    items = [
        OriginInputItem(id="a", credited_origin="CustomOrg", language="en"),
        OriginInputItem(id="b", credited_origin="커스텀기관", language="ko"),
    ]
    res = cluster_origins(items, embedder=FakeEmbedder(), use_embeddings=True)
    assert res.embeddings_used is True
    assert res.independent_lineage_count == 1
    assert res.clusters[0].basis == "embedding"


def test_extract_and_rank_supports_e5_lexical_fallback_and_publisher_caps() -> None:
    docs = [
        DocumentInput(
            url="https://a.example/1",
            publisher="Alpha",
            text=(
                "First paragraph discusses weather.\n\n"
                "Second sentence covers the 2026 budget bill."
            ),
        ),
        DocumentInput(
            url="https://a.example/2",
            publisher="Alpha",
            text="Another Alpha article on the 2026 budget bill.",
        ),
        DocumentInput(
            url="https://a.example/3",
            publisher="Alpha",
            text="Third Alpha article on the 2026 budget bill.",
        ),
        DocumentInput(
            url="https://b.example/1",
            publisher="Beta",
            text="한국 정부는 2026년 예산안을 발표했다.",
        ),
    ]
    # Lexical fallback (no embedder)
    lex_res = extract_and_rank(
        "2026 budget bill",
        docs,
        use_embeddings=False,
        limit=6,
        per_publisher=2,
    )
    assert lex_res.embeddings_used is False
    alpha_count = sum(1 for item in lex_res.excerpts if item.publisher == "Alpha")
    assert alpha_count <= 2
    assert all(item.scoring_method == "lexical" for item in lex_res.excerpts)
    assert all(item.char_end > item.char_start for item in lex_res.excerpts)

    # With FakeEmbedder
    emb_res = extract_and_rank(
        "2026 budget bill",
        docs,
        embedder=FakeEmbedder(),  # type: ignore[arg-type]
        use_embeddings=True,
        limit=6,
        per_publisher=2,
    )
    assert emb_res.embeddings_used is True
    assert emb_res.excerpts[0].publisher == "Beta"
    assert emb_res.excerpts[0].scoring_method == "e5"


def test_local_embedder_skips_uncached_download_by_default(monkeypatch, tmp_path) -> None:
    from btl.embeddings import EmbeddingUnavailableError, LocalEmbedder

    monkeypatch.setenv("HF_HOME", str(tmp_path / "empty-hf"))
    monkeypatch.delenv("BTL_ALLOW_MODEL_DOWNLOAD", raising=False)
    embedder = LocalEmbedder()
    assert embedder.is_cached() is False
    try:
        embedder.similarities(["hello"], ["world"])
    except EmbeddingUnavailableError as exc:
        assert "warmup" in str(exc)
    else:
        raise AssertionError("Expected EmbeddingUnavailableError when uncached")
