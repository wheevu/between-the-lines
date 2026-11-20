"""Integration tests for CLI, bounded MCP compaction, and live stdio JSON-RPC."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from btl.cli import main as cli_main
from btl.mcp_server import handle_message
from btl.service import MAX_RESPONSE_BYTES, compact_payload

REPO_ROOT = Path(__file__).resolve().parents[1]
BIN_BTL = REPO_ROOT / "bin" / "btl"
BIN_MCP = REPO_ROOT / "bin" / "btl-mcp"


def test_cli_check_translation_and_diff_editions(capsys) -> None:
    code = cli_main(
        [
            "check-translation",
            "--source-text",
            "The grant covers 9.5 million residents.",
            "--translation-text",
            "Khoản trợ cấp hỗ trợ 9,5 triệu người dân.",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "clean"

    code2 = cli_main(
        [
            "diff-editions",
            "--before-text",
            "Budget set at 10 million USD in March 2026.",
            "--after-text",
            "Budget set at 12 million USD in April 2026.",
        ]
    )
    assert code2 == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2["changed"] is True


def test_compact_payload_enforces_strict_byte_limit() -> None:
    huge = {
        "claim": "Test claim",
        "excerpts": [
            {
                "excerpt_id": f"e-{i}",
                "excerpt": "word " * 800,
                "explanation": "detail " * 200,
            }
            for i in range(15)
        ],
        "research_ledger_packet": {"huge": "x" * 6000},
        "truncated": False,
        "dropped_fields": [],
    }
    compacted = compact_payload(huge)
    encoded = json.dumps(compacted, ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= MAX_RESPONSE_BYTES
    assert compacted["truncated"] is True
    assert compacted["dropped_fields"]


def test_mcp_handle_message_schema_and_dispatch() -> None:
    init = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init is not None
    assert init["result"]["serverInfo"]["name"] == "btl"

    listed = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    names = [t["name"] for t in listed["result"]["tools"]]
    assert names == [
        "check_translation",
        "analyze_claims",
        "diff_editions",
        "cluster_origins",
        "extract_and_rank",
    ]
    assert "torch" not in sys.modules

    called = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "check_translation",
                "arguments": {
                    "source_text": "The plan costs 10 billion won.",
                    "translation_text": "Kế hoạch tốn 20 tỷ won.",
                },
            },
        }
    )
    assert called is not None
    assert called["result"].get("isError", False) is False
    payload = json.loads(called["result"]["content"][0]["text"])
    assert payload["status"] == "drift_detected"
    assert "torch" not in sys.modules


def test_live_stdio_mcp_subprocess_and_cli_binary() -> None:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "cluster_origins",
                "arguments": {
                    "items": [
                        {"id": "1", "credited_origin": "Yonhap", "language": "en"},
                        {"id": "2", "credited_origin": "연합뉴스", "language": "ko"},
                    ],
                    "emit_research_ledger": True,
                },
            },
        },
    ]
    proc = subprocess.run(
        [str(BIN_MCP)],
        input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 3
    cluster_payload = json.loads(lines[2]["result"]["content"][0]["text"])
    assert cluster_payload["independent_lineage_count"] == 1
    assert cluster_payload["syndication_collapsed"] == 1
    assert len(cluster_payload["research_ledger_origins"]) == 2

    doc_proc = subprocess.run(
        [str(BIN_BTL), "doctor", "--json"],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    doc = json.loads(doc_proc.stdout)
    assert doc["dependencies"]["pydantic"] is True
    assert doc["dependencies"]["trafilatura"] is True
    assert doc["embeddings"]["loaded"] is False
