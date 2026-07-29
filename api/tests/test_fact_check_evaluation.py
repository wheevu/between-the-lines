import csv
import json
from io import StringIO
from pathlib import Path

from app.fact_check_evaluation import (
    CATEGORIES,
    summarize_pool_selection,
    write_pool_selection_sheet,
)


def write_pool(path: Path) -> None:
    cases = []
    for language in ("en", "vi", "ko"):
        for case_index in range(5):
            cases.append(
                {
                    "id": f"{language}-case-{case_index}",
                    "source_language": language,
                    "publisher": "Publisher",
                    "url": "https://example.com/article",
                    "candidates": [
                        {
                            "id": f"{language}-claim-{case_index}-{candidate_index}",
                            "claim_type": "fact",
                            "source_quote": "Exact source quote.",
                            "standalone_claim": "Standalone claim.",
                        }
                        for candidate_index in range(2)
                    ],
                }
            )
    path.write_text(json.dumps({"complete": True, "cases": cases}))


def test_blank_selection_sheet_cannot_be_reported_as_ready(tmp_path: Path) -> None:
    pool = tmp_path / "pool.json"
    selection = tmp_path / "selection.csv"
    write_pool(pool)
    output = StringIO()
    write_pool_selection_sheet(pool, output)
    selection.write_text(output.getvalue())

    summary = summarize_pool_selection(pool, selection)

    assert summary["pool_candidates"] == 30
    assert summary["reviewed_rows"] == 0
    assert summary["selected_claims"] == 0
    assert not summary["ready_for_evidence_adjudication"]
    assert any("Complete all candidate reviews" in item for item in summary["blockers"])


def test_balanced_thirty_claim_selection_passes_all_structural_gates(
    tmp_path: Path,
) -> None:
    pool = tmp_path / "pool.json"
    selection = tmp_path / "selection.csv"
    write_pool(pool)
    output = StringIO()
    write_pool_selection_sheet(pool, output)
    rows = list(csv.DictReader(StringIO(output.getvalue())))
    categories = sorted(CATEGORIES)
    per_language_index = {"en": 0, "vi": 0, "ko": 0}
    for row in rows:
        language = row["source_language"]
        index = per_language_index[language]
        row.update(
            {
                "faithful": "yes",
                "central_checkable": "yes",
                "type_correct": "yes",
                "include_in_30": "yes",
                "primary_category": categories[index // 2],
                "reviewer_id": f"{language}-reviewer",
                "reviewer_role": "independent",
            }
        )
        per_language_index[language] += 1
    with selection.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_pool_selection(pool, selection)

    assert summary["selected_claims"] == 30
    assert summary["selected_by_language"] == {"en": 10, "ko": 10, "vi": 10}
    assert summary["ready_for_evidence_adjudication"]
    assert summary["blockers"] == []


def test_unsafe_selected_claim_is_rejected(tmp_path: Path) -> None:
    pool = tmp_path / "pool.json"
    selection = tmp_path / "selection.csv"
    write_pool(pool)
    output = StringIO()
    write_pool_selection_sheet(pool, output)
    rows = list(csv.DictReader(StringIO(output.getvalue())))
    for row in rows:
        row.update(
            {
                "faithful": "yes",
                "central_checkable": "yes",
                "type_correct": "yes",
                "include_in_30": "no",
                "reviewer_id": "reviewer",
                "reviewer_role": "independent",
            }
        )
    rows[0].update(
        {
            "faithful": "no",
            "include_in_30": "yes",
            "primary_category": "number",
        }
    )
    with selection.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_pool_selection(pool, selection)

    assert summary["selected_claims"] == 0
    assert any("unsafe selections" in item for item in summary["blockers"])


def test_changed_frozen_claim_text_is_rejected(tmp_path: Path) -> None:
    pool = tmp_path / "pool.json"
    selection = tmp_path / "selection.csv"
    write_pool(pool)
    output = StringIO()
    write_pool_selection_sheet(pool, output)
    rows = list(csv.DictReader(StringIO(output.getvalue())))
    for row in rows:
        row.update(
            {
                "faithful": "yes",
                "central_checkable": "yes",
                "type_correct": "yes",
                "include_in_30": "no",
                "reviewer_id": "reviewer",
                "reviewer_role": "independent",
            }
        )
    rows[0]["standalone_claim"] = "A spreadsheet edit changed the frozen claim."
    with selection.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_pool_selection(pool, selection)

    assert not summary["ready_for_evidence_adjudication"]
    assert summary["altered_rows"] == [
        {
            "candidate_id": "en-claim-0-0",
            "fields": ["standalone_claim"],
        }
    ]
    assert "Restore immutable candidate fields from the frozen pool." in summary["blockers"]
