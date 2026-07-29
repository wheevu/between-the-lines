import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.evidence_evaluation import _claim_issues, validate_adjudication


def write_selection(path: Path) -> None:
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["candidate_id", "include_in_30"])
        writer.writeheader()
        for index in range(30):
            writer.writerow(
                {
                    "candidate_id": f"claim-{index}",
                    "include_in_30": "yes",
                }
            )


def claim(index: int, *, complete: bool) -> dict[str, object]:
    language = ("en", "vi", "ko")[index // 10]
    gold = {
        "expected_status": "supported" if complete else None,
        "acceptable_evidence_sets": (
            [
                {
                    "items": [
                        {
                            "url": "https://one.example/report",
                            "publisher": "Publisher One",
                            "language": language,
                            "stance": "supports",
                            "excerpt": "First exact evidence excerpt.",
                            "published_at": "2026-07-01",
                        },
                        {
                            "url": "https://two.example/report",
                            "publisher": "Publisher Two",
                            "language": language,
                            "stance": "supports",
                            "excerpt": "Second exact evidence excerpt.",
                            "published_at": "2026-07-02",
                        },
                    ],
                    "independence_note": "The publishers report independently.",
                }
            ]
            if complete
            else []
        ),
        "checked_at": datetime.now(UTC).isoformat() if complete else None,
        "rationale": "Two independent sources support the claim." if complete else "",
        "search_notes": "",
        "adjudicators": (
            [
                {"id": "reviewer-a", "role": "independent"},
                {"id": "reviewer-b", "role": "independent"},
            ]
            if complete
            else []
        ),
        "adjudication_notes": "",
    }
    return {
        "candidate_id": f"claim-{index}",
        "source_language": language,
        "gold": gold,
    }


def test_incomplete_gold_labels_cannot_be_used_for_system_evaluation(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    write_selection(selection)
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": [claim(index, complete=False) for index in range(30)],
            }
        )
    )

    summary = validate_adjudication(adjudication, selection)

    assert summary["ready_claims"] == 0
    assert not summary["ready_for_system_evaluation"]
    assert len(summary["claim_issues"]) == 30


def test_complete_balanced_gold_labels_pass_structural_validation(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    write_selection(selection)
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )

    summary = validate_adjudication(adjudication, selection)

    assert summary["ready_claims"] == 30
    assert summary["language_counts"] == {"en": 10, "ko": 10, "vi": 10}
    assert summary["ready_for_system_evaluation"]
    assert summary["blockers"] == []


def test_wrong_claim_set_and_unexplained_insufficient_status_are_blocked(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    write_selection(selection)
    claims = [claim(index, complete=True) for index in range(30)]
    claims[0]["candidate_id"] = "not-selected"
    claims[1]["gold"] = {
        "expected_status": "insufficient",
        "acceptable_evidence_sets": [],
        "checked_at": datetime.now(UTC).isoformat(),
        "rationale": "No sufficient evidence was located.",
        "search_notes": "",
        "adjudicators": [
            {"id": "reviewer-a", "role": "independent"},
            {"id": "reviewer-b", "role": "independent"},
        ],
        "adjudication_notes": "",
    }
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": claims,
            }
        )
    )

    summary = validate_adjudication(adjudication, selection)

    assert not summary["ready_for_system_evaluation"]
    assert "Adjudicate the exact candidate IDs in the frozen selection." in summary["blockers"]
    assert summary["claim_issues"] == [
        {
            "candidate_id": "claim-1",
            "issues": ["An insufficient status needs notes describing the search scope."],
        }
    ]


def test_author_and_duplicate_labels_cannot_satisfy_independent_gold() -> None:
    gold = claim(0, complete=True)["gold"]
    gold["adjudicators"] = [
        {"id": "author", "role": "author"},
        {"id": "reviewer-a", "role": "independent"},
        {"id": "reviewer-a", "role": "independent"},
    ]

    assert "Record at least two distinct independent adjudicators." in _claim_issues({"gold": gold})
