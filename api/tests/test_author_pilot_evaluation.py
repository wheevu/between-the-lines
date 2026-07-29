import csv
import json
from hashlib import sha256
from pathlib import Path

from app.author_pilot_evaluation import validate_author_pilot


def _write_selection(path: Path) -> None:
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["candidate_id", "source_language", "include_in_30"],
        )
        writer.writeheader()
        for index in range(30):
            writer.writerow(
                {
                    "candidate_id": f"claim-{index}",
                    "source_language": ("en", "vi", "ko")[index // 10],
                    "include_in_30": "yes",
                }
            )


def _source(source_id: str, host: str, publisher: str) -> dict[str, str]:
    return {
        "id": source_id,
        "url": f"https://{host}/report",
        "publisher": publisher,
        "language": "en",
        "published_at": "2026-07-01",
        "excerpt": "Exact evidence excerpt.",
        "lineage": "Independent publisher report.",
    }


def _claim(index: int, status: str = "supported") -> dict[str, object]:
    return {
        "candidate_id": f"claim-{index}",
        "pilot": {
            "expected_status": status,
            "confidence": "high",
            "supports": ["one", "two"] if status in {"supported", "mixed"} else [],
            "disputes": ["three", "four"] if status in {"disputed", "mixed"} else [],
            "context": [],
            "rationale": "The evidence supports this exploratory label.",
            "search_notes": "Searched publisher and primary-source records.",
        },
    }


def _pilot(selection: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
        "review": {
            "reviewer_role": "author-ai-assisted",
            "checked_at": "2026-07-24T12:00:00+07:00",
        },
        "sources": [
            _source("one", "one.example", "One"),
            _source("two", "two.example", "Two"),
            _source("three", "three.example", "Three"),
            _source("four", "four.example", "Four"),
        ],
        "claims": [_claim(index) for index in range(30)],
    }


def test_complete_author_pilot_passes_without_claiming_independent_gold(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    pilot_path = tmp_path / "pilot.json"
    _write_selection(selection)
    pilot_path.write_text(json.dumps(_pilot(selection)))

    summary = validate_author_pilot(pilot_path, selection)

    assert summary["ready_for_author_pilot"]
    assert not summary["independent_gold_ready"]
    assert summary["ready_claims"] == 30
    assert summary["language_counts"] == {"en": 10, "ko": 10, "vi": 10}


def test_insufficient_claim_requires_search_notes_and_no_resolved_evidence(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    pilot_path = tmp_path / "pilot.json"
    _write_selection(selection)
    data = _pilot(selection)
    data["claims"][0] = _claim(0, "insufficient")
    data["claims"][0]["pilot"]["search_notes"] = ""
    data["claims"][0]["pilot"]["supports"] = ["one"]
    pilot_path.write_text(json.dumps(data))

    summary = validate_author_pilot(pilot_path, selection)

    assert not summary["ready_for_author_pilot"]
    issues = summary["claim_issues"][0]["issues"]
    assert "An insufficient claim cannot have supporting or disputing evidence." in issues
    assert "An insufficient claim needs notes describing the search scope." in issues


def test_mixed_claim_requires_independent_sources_on_both_sides(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    pilot_path = tmp_path / "pilot.json"
    _write_selection(selection)
    data = _pilot(selection)
    data["claims"][0] = _claim(0, "mixed")
    data["claims"][0]["pilot"]["disputes"] = ["three"]
    pilot_path.write_text(json.dumps(data))

    summary = validate_author_pilot(pilot_path, selection)

    assert not summary["ready_for_author_pilot"]
    assert summary["claim_issues"] == [
        {
            "candidate_id": "claim-0",
            "issues": ["Use disputing evidence from at least two publishers and hosts."],
        }
    ]
