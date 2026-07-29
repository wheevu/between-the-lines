import csv
import json
from io import StringIO
from pathlib import Path

from app.claim_evaluation import (
    summarize_claim_reviews,
    write_claim_review_sheet,
)


def write_candidates(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "en-case",
                        "source_language": "en",
                        "url": "https://example.com/article",
                        "candidates": [
                            {
                                "id": f"claim-{index}",
                                "claim_type": "fact",
                                "source_quote": f"Quote {index}",
                                "standalone_claim": f"Claim {index}",
                            }
                            for index in range(1, 4)
                        ],
                    }
                ]
            }
        )
    )


def test_review_sheet_and_summary_do_not_treat_blanks_as_passes(
    tmp_path: Path,
) -> None:
    candidates = tmp_path / "candidates.json"
    reviews = tmp_path / "reviews.csv"
    write_candidates(candidates)
    output = StringIO()
    write_claim_review_sheet(candidates, output)
    reviews.write_text(output.getvalue())

    summary = summarize_claim_reviews(candidates, reviews)

    assert summary["candidate_count"] == 3
    assert summary["reviewed_candidates"] == 0
    assert summary["top_three_success_rate"] is None
    assert summary["blockers"] == ["Review all frozen candidates (0/3 complete)."]


def test_completed_review_reports_top_three_success(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    reviews = tmp_path / "reviews.csv"
    write_candidates(candidates)
    output = StringIO()
    write_claim_review_sheet(candidates, output)
    rows = list(csv.DictReader(StringIO(output.getvalue())))
    for index, row in enumerate(rows):
        row.update(
            {
                "faithful": "yes",
                "central_checkable": "yes" if index == 1 else "no",
                "type_correct": "yes",
                "reviewer_id": "reviewer-1",
                "reviewer_role": "independent",
            }
        )
    with reviews.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_claim_reviews(candidates, reviews)

    assert summary["review_complete"]
    assert summary["top_three_success_rate"] == 1
    assert summary["language_top_three_success_rate"] == {"en": 1.0}
