"""Adapters emitting OpenCode research-ledger/v1 origin batches and candidate packets."""

from __future__ import annotations

from datetime import UTC, datetime

from btl.types import ExtractRankResult, OriginClusterResult


def build_ledger_origins(
    result: OriginClusterResult,
    *,
    origin_ids_by_member: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Build research_ledger(action='origin') batch entries for clustered sources."""
    mapping = origin_ids_by_member or {}
    payload: list[dict[str, str]] = []
    for cluster in result.clusters:
        mapped_members = [mapping.get(mid, mid) for mid in cluster.member_ids]
        if not mapped_members:
            continue
        if len(mapped_members) == 1:
            payload.append(
                {
                    "origin_id": mapped_members[0],
                    "basis": "independent",
                    "independence": "resolved-independent",
                }
            )
            continue
        canonical = mapped_members[0]
        payload.append(
            {
                "origin_id": canonical,
                "basis": "syndication",
                "independence": "resolved-independent",
            }
        )
        for duplicate in mapped_members[1:]:
            if duplicate == canonical:
                continue
            payload.append(
                {
                    "origin_id": duplicate,
                    "basis": "syndication",
                    "independence": "resolved-shared",
                    "canonical": canonical,
                }
            )
    return payload


def build_ledger_packet(
    result: ExtractRankResult,
    *,
    wave: int = 1,
    lane: str = "source-researcher",
    claim_kind: str = "",
) -> dict[str, object]:
    """Build a candidate-only research_ledger worker packet from ranked excerpts."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    sources: list[dict[str, object]] = []
    source_id_by_url: dict[str, str] = {}
    evidence: list[dict[str, object]] = []

    for excerpt in result.excerpts:
        if not excerpt.canonical_url:
            continue
        sid = source_id_by_url.get(excerpt.canonical_url)
        if sid is None:
            sid = f"S{len(sources) + 1}"
            source_id_by_url[excerpt.canonical_url] = sid
            sources.append(
                {
                    "id": sid,
                    "url": excerpt.canonical_url,
                    "title": excerpt.title or excerpt.publisher,
                    "publisher": excerpt.publisher,
                    "tier": 2,
                    "pub_date": "unknown",
                    "update_date": "unknown",
                    "access_date": today,
                    "primary": False,
                    "origin_id": excerpt.cluster_id,
                    "origin_basis": "unresolved",
                    "version": "",
                    "atlas_source_id": "",
                    "source_role": "event_reporting",
                }
            )
        evidence.append(
            {
                "claim_id": "C1",
                "source_id": sid,
                "status": "candidate",
                "locator": {
                    "section": f"chars {excerpt.char_start}-{excerpt.char_end}",
                },
                "passage": excerpt.excerpt[:500],
                "interpretation": (
                    f"Candidate {excerpt.language.value} excerpt ranked by btl "
                    f"({excerpt.scoring_method}, score={excerpt.relevance:.4f})."
                ),
                "stance": "supports",
                "evidence_view": "event_reporting",
                "worker": lane,
                "wave": wave,
            }
        )

    return {
        "task": f"Retrieve candidate cross-lingual excerpts for: {result.claim[:160]}",
        "wave": wave,
        "lane": lane,
        "research_context_used": f"btl extract_and_rank ({result.claim_language.value})",
        "summary": [
            f"Ranked {len(evidence)} candidate excerpt(s) across {len(sources)} source URL(s)."
        ],
        "queries": [],
        "claims": [
            {
                "id": "C1",
                "text": result.claim[:800],
                "load_bearing": True,
                "claim_kind": claim_kind,
                "scope": "",
                "version_range": "",
                "absence": "not_searched" if not evidence else "inconclusive",
                "absence_detail": "",
            }
        ],
        "sources": sources,
        "evidence": evidence,
        "contradictions": [],
        "version_map": [],
        "follow_ups": [],
        "candidate_sources": [],
    }
