"""Zero-dependency stdio JSON-RPC 2.0 MCP server for Between the Lines (`btl`)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from btl import __version__
from btl.service import (
    compact_payload,
    get_embedder,
    run_analyze_claims,
    run_check_translation,
    run_cluster_origins,
    run_diff_editions,
    run_extract_and_rank,
)

SERVER_NAME = "btl"

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "check_translation",
        "description": (
            "Audit EN/VI/KO translation pairs for number/scale mismatches, dropped negations, "
            "modality shifts, legal-stage elevation, attribution loss, and unanchored quotes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_text": {"type": "string", "description": "Single source passage"},
                "translation_text": {"type": "string", "description": "Single translated passage"},
                "source_language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                "target_language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                "source_quote": {"type": "string"},
                "translation_quote": {"type": "string"},
                "pairs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pair_id": {"type": "string"},
                            "source_text": {"type": "string"},
                            "translation_text": {"type": "string"},
                            "source_language": {
                                "type": "string",
                                "enum": ["en", "vi", "ko", "auto"],
                            },
                            "target_language": {
                                "type": "string",
                                "enum": ["en", "vi", "ko", "auto"],
                            },
                            "source_quote": {"type": "string"},
                            "translation_quote": {"type": "string"},
                        },
                        "required": ["source_text", "translation_text"],
                    },
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_claims",
        "description": (
            "Segment EN/VI/KO text, extract modality/legal/number/date/negation facets, "
            "verify candidate claim grounding, and check multilingual search queries."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "source_quote": {"type": "string"},
                            "standalone_claim": {"type": "string"},
                            "segment_ids": {"type": "array", "items": {"type": "string"}},
                            "entities": {"type": "array", "items": {"type": "string"}},
                            "dates": {"type": "array", "items": {"type": "string"}},
                            "numbers": {"type": "array", "items": {"type": "string"}},
                            "attribution": {"type": "string"},
                        },
                        "required": ["source_quote", "standalone_claim"],
                    },
                },
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "language": {"type": "string", "enum": ["en", "vi", "ko"]},
                            "exact_query": {"type": "string"},
                            "context_query": {"type": "string"},
                        },
                        "required": ["language", "exact_query"],
                    },
                },
                "max_segments": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "diff_editions",
        "description": (
            "Compare two versions of an article, policy, or statute across numbers, dates, "
            "negations, names, modality, legal state, and terminology with SHA-256 hashes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "before_text": {"type": "string"},
                "after_text": {"type": "string"},
                "before_language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                "after_language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
            },
            "required": ["before_text", "after_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cluster_origins",
        "description": (
            "Group EN/VI/KO sources sharing a credited wire/org alias, acronym, near-duplicate "
            "text, or optional E5 similarity so syndication does not inflate independence."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "url": {"type": "string"},
                            "publisher": {"type": "string"},
                            "credited_origin": {"type": "string"},
                            "language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                            "excerpt": {"type": "string"},
                            "title": {"type": "string"},
                        },
                    },
                },
                "use_embeddings": {"type": "boolean"},
                "emit_research_ledger": {"type": "boolean"},
                "origin_ids_by_member": {"type": "object"},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "name": "extract_and_rank",
        "description": (
            "Fetch public HTML URLs safely (SSRF-guarded) or ingest supplied text, chunk "
            "EN/VI/KO passages with offsets, and rank top excerpts with publisher caps."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "claim_language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                "urls": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                "documents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "title": {"type": "string"},
                            "publisher": {"type": "string"},
                            "published_at": {"type": "string"},
                            "text": {"type": "string"},
                            "language": {"type": "string", "enum": ["en", "vi", "ko", "auto"]},
                        },
                        "required": ["text"],
                    },
                },
                "input_url": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "per_publisher": {"type": "integer", "minimum": 1, "maximum": 5},
                "use_embeddings": {"type": "boolean"},
                "emit_research_ledger_packet": {"type": "boolean"},
                "wave": {"type": "integer", "minimum": 1},
                "lane": {"type": "string"},
                "claim_kind": {"type": "string"},
            },
            "required": ["claim"],
            "additionalProperties": False,
        },
    },
]

TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "check_translation": run_check_translation,
    "analyze_claims": run_analyze_claims,
    "diff_editions": run_diff_editions,
    "cluster_origins": run_cluster_origins,
    "extract_and_rank": run_extract_and_rank,
}


def handle_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Process one JSON-RPC 2.0 request and return a response dict (or None for notifications)."""
    has_id = "id" in msg and msg["id"] is not None
    req_id = msg.get("id")
    method = msg.get("method") if isinstance(msg.get("method"), str) else ""

    if not has_id:
        return None

    if method == "initialize":
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        requested = params.get("protocolVersion")
        protocol = requested if isinstance(requested, str) and requested else "2024-11-05"
        return _result(
            req_id,
            {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
            },
        )

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": TOOL_SPECS})

    if method == "tools/call":
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        tool_name = str(params.get("name") or "")
        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return _error(req_id, -32602, f"Unknown tool: {tool_name}")
        raw_args = params.get("arguments")
        if raw_args is None:
            arguments: dict[str, Any] = {}
        elif isinstance(raw_args, dict):
            arguments = raw_args
        else:
            return _result(
                req_id,
                {
                    "content": [{"type": "text", "text": "Tool arguments must be a JSON object."}],
                    "isError": True,
                },
            )
        try:
            raw_out = handler(arguments)
            bounded = compact_payload(raw_out)
            return _result(
                req_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(bounded, ensure_ascii=False)}
                    ]
                },
            )
        except Exception as error:
            return _result(
                req_id,
                {
                    "content": [{"type": "text", "text": str(error)}],
                    "isError": True,
                },
            )

    return _error(req_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        trimmed = line.strip()
        if not trimmed:
            continue
        try:
            msg = json.loads(trimmed)
            if not isinstance(msg, dict):
                _send(_error(None, -32600, "Invalid Request"))
                continue
        except json.JSONDecodeError:
            _send(_error(None, -32700, "Parse error"))
            continue

        response = handle_message(msg)
        if response is not None:
            _send(response)
        get_embedder().maybe_unload_idle()
    return 0


def _result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
