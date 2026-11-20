#!/usr/bin/env python3
"""Generate site/data/cases.json by executing btl.service functions directly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from btl.service import (  # noqa: E402
    run_check_translation,
    run_cluster_origins,
    run_diff_editions,
    run_doctor,
    run_extract_and_rank,
)

OUT = ROOT / "site" / "data" / "cases.json"


def build_cases() -> dict:
    case_1_input = {
        "source_text": "예산은 4월에 1억 5000만 원에 달했다.",
        "translation_text": "Ngân sách đạt 150 triệu won vào tháng 4.",
        "source_language": "ko",
        "target_language": "vi",
    }
    case_2_input = {
        "source_text": (
            "The fund did not approve the $150 million allocation, and regulators "
            "opened an investigation into the allegation."
        ),
        "translation_text": (
            "Quỹ đã phê duyệt khoản phân bổ 15 triệu USD và cơ quan quản lý đã "
            "ra phán quyết về vụ việc."
        ),
        "source_language": "en",
        "target_language": "vi",
    }
    case_3_input = {
        "source_text": "The regulator may delay approval if filings remain incomplete.",
        "translation_text": "Cơ quan quản lý đã chính thức phê duyệt hồ sơ.",
        "source_language": "en",
        "target_language": "vi",
        "source_quote": "may delay approval",
        "translation_quote": "đã phê duyệt ngay",
    }
    case_4_input = {
        "before_text": (
            "Investors may not redeem shares before March 15, 2026. The minimum "
            "commitment is $250,000, and the fee waiver remains under review."
        ),
        "after_text": (
            "Investors may redeem shares after April 1, 2026. The minimum "
            "commitment is $500,000, and the fee waiver is approved."
        ),
        "before_language": "en",
        "after_language": "en",
    }
    case_5_input = {
        "items": [
            {
                "item_id": "a1",
                "url": "https://reuters.example/1",
                "publisher": "Reuters",
                "title": "Global temperatures hit record",
                "excerpt": "WMO said global temperatures reached a new peak in October.",
                "credited_origin": "WMO",
            },
            {
                "item_id": "a2",
                "url": "https://korea.example/2",
                "publisher": "연합뉴스",
                "title": "기온 사상 최고",
                "excerpt": (
                    "세계기상기구(WMO)는 10월 지구 평균 기온이 사상 최고치를 "
                    "기록했다고 밝혔다."
                ),
                "credited_origin": "세계기상기구",
            },
            {
                "item_id": "a3",
                "url": "https://vn.example/3",
                "publisher": "TTXVN",
                "title": "Nhiệt độ toàn cầu lập kỷ lục",
                "excerpt": (
                    "Tổ chức Khí tượng Thế giới (WMO) cho biết nhiệt độ tháng 10 "
                    "đạt mức cao mới."
                ),
                "credited_origin": "WMO",
            },
            {
                "item_id": "a4",
                "url": "https://local.example/4",
                "publisher": "Local Ledger",
                "title": "City flood defenses",
                "excerpt": "City engineers inspected coastal barriers ahead of November tides.",
                "credited_origin": "City Engineering Office",
            },
        ],
        "emit_research_ledger": True,
    }
    case_6_input = {
        "claim": "The minimum commitment increased to $500,000 after April 1, 2026.",
        "documents": [
            {
                "url": "https://docs.example/memo-v2",
                "title": "Fund Addendum v2",
                "publisher": "Operations Desk",
                "text": (
                    "Effective April 1, 2026, the minimum investor commitment is $500,000 "
                    "and redemptions are permitted quarterly. Earlier fee waivers are now approved."
                ),
            },
            {
                "url": "https://docs.example/mirror",
                "title": "Fund Addendum Mirror",
                "publisher": "Operations Desk",
                "text": (
                    "Effective April 1, 2026, the minimum investor commitment is $500,000 "
                    "and redemptions are permitted quarterly. Earlier fee waivers are now approved."
                ),
            },
            {
                "url": "https://docs.example/faq",
                "title": "Investor FAQ",
                "publisher": "Client Relations",
                "text": (
                    "Standard onboarding takes three business days once KYC verification is "
                    "complete. Minimum commitment rules follow the latest addendum."
                ),
            },
        ],
        "use_embeddings": False,
        "emit_research_ledger_packet": True,
    }

    doctor = run_doctor({})
    cases = [
        {
            "id": "ko-vi-scale-clean",
            "category": "translation",
            "tool": "check_translation",
            "title": "Cross-script scale equivalence (KO -> VI)",
            "subtitle": "1억 5000만 원 == 150 triệu won",
            "badge": "CLEAN",
            "tone": "clean",
            "summary": (
                "Normalizes Korean (억/만) and Vietnamese (triệu) number scales to exact Decimal "
                "values, avoiding false positives across scripts."
            ),
            "command": (
                './bin/btl check-translation --source-text "예산은 4월에 1억 5000만 원에 달했다." '
                '--translation-text "Ngân sách đạt 150 triệu won vào tháng 4."'
            ),
            "input": case_1_input,
            "highlights": {
                "source": ["1억 5000만 원"],
                "translation": ["150 triệu won"],
            },
            "output": run_check_translation(case_1_input),
        },
        {
            "id": "fund-allocation-drift",
            "category": "translation",
            "tool": "check_translation",
            "title": "Financial & legal drift caught (EN -> VI)",
            "subtitle": "$150M -> 15M, dropped 'not', investigation -> ruling",
            "badge": "3 FLAGS",
            "tone": "alert",
            "summary": (
                "Flags three high-impact errors in one pass: a 10x drop in capital amount, "
                "an inverted approval decision, and an elevated legal status."
            ),
            "command": (
                "./bin/btl check-translation "
                '--source-text "The fund did not approve the $150 million allocation, and '
                'regulators opened an investigation into the allegation." '
                '--translation-text "Quỹ đã phê duyệt khoản phân bổ 15 triệu USD và cơ quan '
                'quản lý đã ra phán quyết về vụ việc."'
            ),
            "input": case_2_input,
            "highlights": {
                "source": ["did not", "$150 million", "investigation"],
                "translation": ["15 triệu USD", "phán quyết"],
            },
            "output": run_check_translation(case_2_input),
        },
        {
            "id": "modality-unanchored-quote",
            "category": "translation",
            "tool": "check_translation",
            "title": "Modality shift & unanchored quote (EN -> VI)",
            "subtitle": "'may delay' -> 'officially approved' + missing quote",
            "badge": "2 FLAGS",
            "tone": "alert",
            "summary": (
                "Detects hedged language ('may') turned into an asserted fact and rejects a "
                "supplied citation quote that does not appear verbatim in the translation."
            ),
            "command": (
                "./bin/btl check-translation --payload "
                '\'{"source_text":"The regulator may delay approval if filings remain incomplete.",'
                '"translation_text":"Cơ quan quản lý đã chính thức phê duyệt hồ sơ.",...}\''
            ),
            "input": case_3_input,
            "highlights": {
                "source": ["may delay"],
                "translation": ["đã chính thức phê duyệt"],
            },
            "output": run_check_translation(case_3_input),
        },
        {
            "id": "redemption-clause-diff",
            "category": "diff",
            "tool": "diff_editions",
            "title": "Fund redemption clause revision diff",
            "subtitle": "Number, date, negation, and terminology changes",
            "badge": "4 CHANGES",
            "tone": "alert",
            "summary": (
                "Compares two document versions with SHA-256 digests and classifies every change "
                "into numbers, dates, polarity markers, and legal/policy terminology."
            ),
            "command": (
                './bin/btl diff-editions --before-text "Investors may not redeem shares '
                'before March 15, 2026..." --after-text "Investors may redeem shares '
                'after April 1, 2026..."'
            ),
            "input": case_4_input,
            "highlights": {
                "before": ["not", "March 15, 2026", "$250,000", "remains under review"],
                "after": ["April 1, 2026", "$500,000", "approved"],
            },
            "output": run_diff_editions(case_4_input),
        },
        {
            "id": "cross-script-wire-clustering",
            "category": "lineage",
            "tool": "cluster_origins",
            "title": "Cross-script wire syndication clustering",
            "subtitle": "Reuters + 연합뉴스 + TTXVN -> 1 shared WMO origin",
            "badge": "2 LINEAGES",
            "tone": "clean",
            "summary": (
                "Resolves English, Korean (세계기상기구), and Vietnamese aliases to the same "
                "canonical origin so syndicated wire stories are not counted as independent."
            ),
            "command": "./bin/btl cluster-origins --payload-stdin < wire_sources.json",
            "input": case_5_input,
            "output": run_cluster_origins(case_5_input),
        },
        {
            "id": "deduped-passage-ranking",
            "category": "lineage",
            "tool": "extract_and_rank",
            "title": "Near-duplicate dedupe & passage ranking",
            "subtitle": "3 docs -> mirror collapsed, 2 candidate excerpts",
            "badge": "2 RANKED",
            "tone": "clean",
            "summary": (
                "Deduplicates mirrored addendum text before ranking relevant passages against the "
                "claim, emitting candidate-only provenance records with exact character offsets."
            ),
            "command": "./bin/btl extract-and-rank --payload-stdin < claim_docs.json",
            "input": case_6_input,
            "output": run_extract_and_rank(case_6_input),
        },
    ]

    return {
        "version": doctor["version"],
        "harnesses": doctor["harnesses"],
        "dependencies": doctor["dependencies"],
        "cases": cases,
    }


def normalize_for_check(payload: dict) -> dict:
    """Strip environment- and date-dependent fields before comparing outputs."""
    data = json.loads(json.dumps(payload))
    data.pop("harnesses", None)
    for case in data.get("cases", []):
        packet = case.get("output", {}).get("research_ledger_packet")
        if isinstance(packet, dict):
            for source in packet.get("sources", []):
                if isinstance(source, dict):
                    source.pop("access_date", None)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify site/data/cases.json matches.")
    args = parser.parse_args()

    payload = build_cases()
    if args.check:
        if not OUT.exists():
            raise SystemExit(f"Missing {OUT.relative_to(ROOT)}")
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        if normalize_for_check(existing) != normalize_for_check(payload):
            raise SystemExit(
                f"{OUT.relative_to(ROOT)} is stale; run python3 scripts/generate_site_data.py"
            )
        print(
            f"OK: {OUT.relative_to(ROOT)} matches current btl outputs "
            f"({len(payload['cases'])} cases)"
        )
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(payload['cases'])} cases)")


if __name__ == "__main__":
    main()
