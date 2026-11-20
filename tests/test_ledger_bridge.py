"""Tests verifying emitted packets and origin batches match OpenCode research_ledger.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from btl.ledger_bridge import build_ledger_origins, build_ledger_packet
from btl.lineage import cluster_origins
from btl.ranker import extract_and_rank
from btl.types import DocumentInput, OriginInputItem

RESEARCH_LEDGER_SCRIPT = Path.home() / ".config" / "opencode" / "scripts" / "research_ledger.py"


def _load_research_ledger():
    if not RESEARCH_LEDGER_SCRIPT.is_file():
        pytest.skip("OpenCode research_ledger.py not present on this machine")
    spec = importlib.util.spec_from_file_location("oc_research_ledger", RESEARCH_LEDGER_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emitted_packet_and_origins_ingest_into_research_ledger_cleanly() -> None:
    rl = _load_research_ledger()

    docs = [
        DocumentInput(
            url="https://reuters.example/story",
            title="Policy Passed",
            publisher="Reuters",
            text="South Korea passed a 15 billion won subsidy bill in March 2026.",
            language="en",
        ),
        DocumentInput(
            url="https://yonhap.example/story",
            title="보조금 통과",
            publisher="Yonhap",
            text="한국 국회는 2026년 3월 150억 원 규모 보조금 법안을 통과시켰다.",
            language="ko",
        ),
    ]
    rank_res = extract_and_rank(
        "South Korea passed a 15 billion won subsidy bill in March 2026.",
        docs,
        use_embeddings=False,
    )
    packet = build_ledger_packet(rank_res, wave=1, lane="source-researcher")
    assert all(ev["status"] == "candidate" for ev in packet["evidence"])

    ledger = rl.new_ledger("Did South Korea pass the 15B KRW subsidy bill?")
    summary = rl.ingest_packet(ledger, packet)
    assert summary["rejected"] == []
    assert summary["claims"] == 1
    assert summary["sources"] == 2
    assert summary["evidence"] == 2

    # Now map the ledger's assigned origin IDs through cluster_origins
    origin_items = []
    origin_ids_by_member = {}
    for sid, src in ledger["sources"].items():
        origin_items.append(
            OriginInputItem(
                id=sid,
                url=src["canonical_url"],
                publisher=src["publisher"],
                credited_origin="Reuters" if "reuters" in src["canonical_url"] else "로이터",
            )
        )
        origin_ids_by_member[sid] = src["origin_id"]

    clusters = cluster_origins(origin_items)
    origin_batch = build_ledger_origins(clusters, origin_ids_by_member=origin_ids_by_member)
    for entry in origin_batch:
        rl.set_origin(
            ledger,
            entry["origin_id"],
            entry["basis"],
            entry["independence"],
            entry.get("canonical", ""),
        )
    # Two syndicated handles now resolve to one canonical origin root
    roots = {rl.origin_root(ledger, src["origin_id"]) for src in ledger["sources"].values()}
    assert len(roots) == 1
