"""Deterministic JSON CLI for Between the Lines."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from typing import Any

from btl.service import (
    compact_payload,
    run_analyze_claims,
    run_check_translation,
    run_cluster_origins,
    run_diff_editions,
    run_doctor,
    run_extract_and_rank,
    run_warmup,
)

HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "check-translation": run_check_translation,
    "analyze-claims": run_analyze_claims,
    "diff-editions": run_diff_editions,
    "cluster-origins": run_cluster_origins,
    "extract-and-rank": run_extract_and_rank,
    "warmup": run_warmup,
    "doctor": run_doctor,
}


def build_parser() -> argparse.ArgumentParser:
    epilog = (
        "Examples:\n"
        "  btl check-translation --payload '{\"source_text\":\"9.5 million\","
        "\"translation_text\":\"950만\"}'\n"
        "  btl analyze-claims --payload-stdin < claim_input.json\n"
        "  btl diff-editions --before-text \"...\" --after-text \"...\"\n"
        "  btl cluster-origins --payload-stdin < origins.json\n"
        "  btl extract-and-rank --claim \"<claim>\" --url <url>\n"
        "  btl doctor --json\n"
    )
    parser = argparse.ArgumentParser(
        prog="btl",
        description="Local EN/VI/KO verification, origin clustering, and passage ranking CLI.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd in HANDLERS:
        sp = sub.add_parser(cmd)
        sp.add_argument("--payload", help="JSON request payload string")
        sp.add_argument(
            "--payload-stdin",
            action="store_true",
            help="Read JSON request payload from stdin",
        )
        sp.add_argument("--full", action="store_true", help="Disable byte truncation")
        sp.add_argument("--json", action="store_true", help="Emit JSON output (default)")
        if cmd == "check-translation":
            sp.add_argument("--source-text")
            sp.add_argument("--translation-text")
            sp.add_argument("--source-language", default="auto")
            sp.add_argument("--target-language", default="auto")
        elif cmd == "analyze-claims":
            sp.add_argument("--text")
            sp.add_argument("--language", default="auto")
        elif cmd == "diff-editions":
            sp.add_argument("--before-text")
            sp.add_argument("--after-text")
            sp.add_argument("--before-language", default="auto")
            sp.add_argument("--after-language", default="auto")
        elif cmd == "extract-and-rank":
            sp.add_argument("--claim")
            sp.add_argument("--url", action="append", dest="urls")
            sp.add_argument("--no-embeddings", action="store_true")
            sp.add_argument("--limit", type=int, default=6)
    return parser


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "payload", None) and getattr(args, "payload_stdin", False):
        raise ValueError("Pass either --payload or --payload-stdin, not both.")
    payload: dict[str, Any] = {}
    if getattr(args, "payload_stdin", False):
        raw = sys.stdin.read()
        if raw.strip():
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise ValueError("Stdin payload must be a JSON object.")
            payload = loaded
    elif getattr(args, "payload", None):
        loaded = json.loads(args.payload)
        if not isinstance(loaded, dict):
            raise ValueError("--payload must be a JSON object.")
        payload = loaded

    if args.command == "check-translation":
        if getattr(args, "source_text", None):
            payload.setdefault("source_text", args.source_text)
        if getattr(args, "translation_text", None):
            payload.setdefault("translation_text", args.translation_text)
        if "source_language" not in payload and getattr(args, "source_language", None):
            payload["source_language"] = args.source_language
        if "target_language" not in payload and getattr(args, "target_language", None):
            payload["target_language"] = args.target_language
    elif args.command == "analyze-claims":
        if getattr(args, "text", None):
            payload.setdefault("text", args.text)
        if "language" not in payload and getattr(args, "language", None):
            payload["language"] = args.language
    elif args.command == "diff-editions":
        if getattr(args, "before_text", None):
            payload.setdefault("before_text", args.before_text)
        if getattr(args, "after_text", None):
            payload.setdefault("after_text", args.after_text)
        if "before_language" not in payload and getattr(args, "before_language", None):
            payload["before_language"] = args.before_language
        if "after_language" not in payload and getattr(args, "after_language", None):
            payload["after_language"] = args.after_language
    elif args.command == "extract-and-rank":
        if getattr(args, "claim", None):
            payload.setdefault("claim", args.claim)
        if getattr(args, "urls", None):
            payload.setdefault("urls", args.urls)
        if getattr(args, "no_embeddings", False):
            payload["use_embeddings"] = False
        if "limit" not in payload and getattr(args, "limit", None) is not None:
            payload["limit"] = args.limit
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_payload(args)
        result = HANDLERS[args.command](payload)
        bounded = compact_payload(result, full=bool(args.full))
        sys.stdout.write(json.dumps(bounded, ensure_ascii=False, indent=2) + "\n")
        return 0
    except Exception as error:
        err_payload = {
            "error": str(error),
            "command": args.command,
        }
        sys.stderr.write(json.dumps(err_payload, ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
