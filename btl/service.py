"""Shared operation dispatch, doctor diagnostics, and byte-bounded compaction."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from btl import __version__
from btl.claims import analyze_claims
from btl.embeddings import LocalEmbedder
from btl.extractor import fetch_batch
from btl.fact_guard import audit_translations
from btl.ledger_bridge import build_ledger_origins, build_ledger_packet
from btl.lineage import cluster_origins
from btl.provenance import diff_editions
from btl.ranker import extract_and_rank
from btl.types import (
    ClaimInput,
    DocumentInput,
    OriginInputItem,
    SearchQueryInput,
    TranslationPairInput,
)

MAX_RESPONSE_BYTES = 9_500
REPO_ROOT = Path(__file__).resolve().parents[1]

_SHARED_EMBEDDER: LocalEmbedder | None = None


def get_embedder() -> LocalEmbedder:
    global _SHARED_EMBEDDER
    if _SHARED_EMBEDDER is None:
        _SHARED_EMBEDDER = LocalEmbedder()
    return _SHARED_EMBEDDER


def run_check_translation(args: dict[str, Any]) -> dict[str, Any]:
    raw_pairs = args.get("pairs")
    if not raw_pairs:
        if "source_text" in args and "translation_text" in args:
            raw_pairs = [
                {
                    "pair_id": args.get("pair_id"),
                    "source_text": args["source_text"],
                    "translation_text": args["translation_text"],
                    "source_language": args.get("source_language", "auto"),
                    "target_language": args.get("target_language", "auto"),
                    "source_quote": args.get("source_quote"),
                    "translation_quote": args.get("translation_quote"),
                }
            ]
        else:
            raise ValueError("Provide either 'pairs' or both 'source_text' and 'translation_text'.")
    pairs = [TranslationPairInput.model_validate(item) for item in raw_pairs]
    result = audit_translations(pairs)
    return result.model_dump(mode="json")


def run_analyze_claims(args: dict[str, Any]) -> dict[str, Any]:
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'text' must be a non-empty string.")
    claims = [ClaimInput.model_validate(item) for item in (args.get("claims") or [])]
    queries = [SearchQueryInput.model_validate(item) for item in (args.get("queries") or [])]
    max_segments = int(args.get("max_segments", 80))
    result = analyze_claims(
        text,
        language=args.get("language", "auto"),
        claims=claims,
        queries=queries,
        max_segments=max(1, min(max_segments, 200)),
    )
    return result.model_dump(mode="json")


def run_diff_editions(args: dict[str, Any]) -> dict[str, Any]:
    before_text = args.get("before_text")
    after_text = args.get("after_text")
    if not isinstance(before_text, str) or not isinstance(after_text, str):
        raise ValueError("Both 'before_text' and 'after_text' strings are required.")
    result = diff_editions(
        before_text,
        after_text,
        before_language=args.get("before_language", "auto"),
        after_language=args.get("after_language", "auto"),
    )
    return result.model_dump(mode="json")


def run_cluster_origins(args: dict[str, Any]) -> dict[str, Any]:
    raw_items = args.get("items") or []
    items = [OriginInputItem.model_validate(item) for item in raw_items]
    use_embeddings = bool(args.get("use_embeddings", False))
    embedder = get_embedder() if use_embeddings else None
    result = cluster_origins(items, embedder=embedder, use_embeddings=use_embeddings)
    if args.get("emit_research_ledger"):
        raw_map = args.get("origin_ids_by_member")
        origin_map = dict(raw_map) if isinstance(raw_map, dict) else None
        result = result.model_copy(
            update={
                "research_ledger_origins": build_ledger_origins(
                    result, origin_ids_by_member=origin_map
                )
            }
        )
    if embedder is not None:
        embedder.maybe_unload_idle()
    return result.model_dump(mode="json")


def run_extract_and_rank(args: dict[str, Any]) -> dict[str, Any]:
    claim = args.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("'claim' must be a non-empty string.")
    urls = [str(u) for u in (args.get("urls") or [])]
    docs = [DocumentInput.model_validate(item) for item in (args.get("documents") or [])]
    if not urls and not docs:
        raise ValueError("Provide at least one 'urls' entry or 'documents' entry.")

    failures = []
    if urls:
        fetched_docs, failures = fetch_batch(
            urls,
            input_url=args.get("input_url"),
            limit=max(1, min(int(args.get("max_pages", 12)), 12)),
            max_per_publisher=max(1, min(int(args.get("max_per_publisher", 3)), 5)),
        )
        for fetched in fetched_docs:
            docs.append(
                DocumentInput(
                    url=fetched.canonical_url,
                    title=fetched.title,
                    publisher=fetched.publisher,
                    published_at=fetched.published_at_unverified,
                    text=fetched.text,
                    language="auto",
                )
            )

    use_embeddings = bool(args.get("use_embeddings", True))
    embedder = get_embedder() if use_embeddings else None
    result = extract_and_rank(
        claim,
        docs,
        claim_language=args.get("claim_language", "auto"),
        failures=failures,
        limit=max(1, min(int(args.get("limit", 6)), 20)),
        per_publisher=max(1, min(int(args.get("per_publisher", 2)), 5)),
        embedder=embedder,
        use_embeddings=use_embeddings,
    )
    if args.get("emit_research_ledger_packet"):
        packet = build_ledger_packet(
            result,
            wave=int(args.get("wave", 1)),
            lane=str(args.get("lane", "source-researcher")),
            claim_kind=str(args.get("claim_kind", "")),
        )
        result = result.model_copy(update={"research_ledger_packet": packet})
    if embedder is not None:
        embedder.maybe_unload_idle()
    return result.model_dump(mode="json")


def run_warmup(_: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_embedder().warmup()


def run_doctor(_: dict[str, Any] | None = None) -> dict[str, Any]:
    home = Path.home()
    opencode_cfg = home / ".config" / "opencode" / "opencode.json"
    t3_agy_cfg = (
        home
        / ".t3"
        / "userdata"
        / "providers"
        / "antigravity"
        / "ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32"
        / "config"
        / "mcp_config.json"
    )
    agy_cfg = home / ".gemini" / "config" / "mcp_config.json"
    codex_cfg = home / ".codex" / "config.toml"
    shared_skill = home / ".agents" / "skills" / "between-the-lines" / "SKILL.md"

    return {
        "version": __version__,
        "repo_root": str(REPO_ROOT),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "dependencies": {
            pkg: importlib.util.find_spec(pkg) is not None
            for pkg in ("httpx", "pydantic", "trafilatura")
        },
        "embeddings": get_embedder().status(),
        "harnesses": {
            "opencode_mcp": _json_has_key(opencode_cfg, ("mcp", "btl")),
            "t3_antigravity_mcp": _json_has_key(t3_agy_cfg, ("mcpServers", "btl")),
            "agy_cli_mcp": _json_has_key(agy_cfg, ("mcpServers", "btl")),
            "codex_mcp": _toml_has_btl(codex_cfg),
            "shared_skill": shared_skill.is_file(),
        },
    }


def compact_payload(
    payload: dict[str, Any],
    *,
    max_bytes: int = MAX_RESPONSE_BYTES,
    full: bool = False,
) -> dict[str, Any]:
    """Ensure JSON payload stays under `max_bytes` UTF-8 with structured truncation info."""
    if full or _encoded_bytes(payload) <= max_bytes:
        return payload

    data = json.loads(json.dumps(payload, ensure_ascii=False))
    dropped: list[str] = list(data.get("dropped_fields") or [])

    for optional_key in ("research_ledger_packet", "research_ledger_origins", "failures"):
        if optional_key in data and data[optional_key]:
            data[optional_key] = None if optional_key != "failures" else []
            if optional_key not in dropped:
                dropped.append(optional_key)
            data["truncated"] = True
            data["dropped_fields"] = dropped
            if _encoded_bytes(data) <= max_bytes:
                return data

    # Trim oversized text fields inside list containers, then pop trailing items.
    for list_key in ("excerpts", "segments", "pairs", "clusters", "changes", "claim_checks"):
        items = data.get(list_key)
        if not isinstance(items, list) or not items:
            continue
        for item in items:
            if isinstance(item, dict):
                for text_key in (
                    "excerpt",
                    "text",
                    "explanation",
                    "source_quote",
                    "translation_quote",
                ):
                    val = item.get(text_key)
                    if isinstance(val, str) and len(val) > 300:
                        item[text_key] = val[:297] + "..."
                for seq_key in (
                    "source_numbers",
                    "translation_numbers",
                    "added",
                    "removed",
                    "origins_seen",
                    "urls",
                ):
                    seq = item.get(seq_key)
                    if isinstance(seq, list) and len(seq) > 25:
                        item[seq_key] = seq[:25]
        data["truncated"] = True
        if list_key not in dropped:
            dropped.append(list_key)
        data["dropped_fields"] = dropped
        if _encoded_bytes(data) <= max_bytes:
            return data

        while len(items) > 1 and _encoded_bytes(data) > max_bytes:
            items.pop()
        if _encoded_bytes(data) <= max_bytes:
            return data

    # Final safety clamp if a single remaining entry still pushes past max_bytes.
    for list_key in ("excerpts", "segments", "pairs", "clusters", "changes", "claim_checks"):
        items = data.get(list_key)
        if isinstance(items, list) and items and isinstance(items[0], dict):
            for text_key in ("excerpt", "text", "explanation", "source_quote", "translation_quote"):
                val = items[0].get(text_key)
                if isinstance(val, str) and len(val) > 120:
                    items[0][text_key] = val[:117] + "..."
        if _encoded_bytes(data) <= max_bytes:
            return data

    if _encoded_bytes(data) > max_bytes:
        for list_key in ("excerpts", "segments", "pairs", "clusters", "changes", "claim_checks"):
            if isinstance(data.get(list_key), list) and data[list_key]:
                data[list_key] = []
                if list_key not in dropped:
                    dropped.append(list_key)
                data["truncated"] = True
                data["dropped_fields"] = dropped
                if _encoded_bytes(data) <= max_bytes:
                    return data
    return data


def _encoded_bytes(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _json_has_key(path: Path, keys: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    try:
        cur: Any = json.loads(path.read_text(encoding="utf-8"))
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                return False
            cur = cur[key]
        return True
    except Exception:
        return False


def _toml_has_btl(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcp_servers", {})
        return isinstance(servers, dict) and "btl" in servers
    except Exception:
        return False
