import csv
import json
from collections import Counter
from pathlib import Path
from typing import TextIO

SELECTION_FIELDS = [
    "case_id",
    "source_language",
    "publisher",
    "source_url",
    "candidate_rank",
    "candidate_id",
    "claim_type",
    "source_quote",
    "standalone_claim",
    "faithful",
    "central_checkable",
    "type_correct",
    "include_in_30",
    "primary_category",
    "reviewer_id",
    "reviewer_role",
    "notes",
]
JUDGMENTS = {"yes", "no", "unsure"}
CATEGORIES = {
    "number",
    "date",
    "legal-attribution",
    "direct-announcement",
    "abstention",
}
LANGUAGES = {"en", "vi", "ko"}


def write_pool_selection_sheet(pool_path: Path, output: TextIO) -> None:
    pool = json.loads(pool_path.read_text())
    if pool.get("complete") is not True:
        raise ValueError("The claim pool is incomplete.")
    writer = csv.DictWriter(output, fieldnames=SELECTION_FIELDS)
    writer.writeheader()
    for case in pool["cases"]:
        for rank, candidate in enumerate(case["candidates"], start=1):
            writer.writerow(
                {
                    "case_id": case["id"],
                    "source_language": case["source_language"],
                    "publisher": case["publisher"],
                    "source_url": case["url"],
                    "candidate_rank": rank,
                    "candidate_id": candidate["id"],
                    "claim_type": candidate["claim_type"],
                    "source_quote": candidate["source_quote"],
                    "standalone_claim": candidate["standalone_claim"],
                    "faithful": "",
                    "central_checkable": "",
                    "type_correct": "",
                    "include_in_30": "",
                    "primary_category": "",
                    "reviewer_id": "",
                    "reviewer_role": "",
                    "notes": "",
                }
            )


def summarize_pool_selection(
    pool_path: Path,
    selection_path: Path,
) -> dict[str, object]:
    pool = json.loads(pool_path.read_text())
    expected = {
        candidate["id"]: {
            "case_id": case["id"],
            "source_language": case["source_language"],
            "publisher": case["publisher"],
            "source_url": case["url"],
            "candidate_rank": str(rank),
            "claim_type": candidate["claim_type"],
            "source_quote": candidate["source_quote"],
            "standalone_claim": candidate["standalone_claim"],
        }
        for case in pool["cases"]
        for rank, candidate in enumerate(case["candidates"], start=1)
    }
    with selection_path.open(newline="") as source:
        rows = list(csv.DictReader(source))

    candidate_counts = Counter(row.get("candidate_id", "") for row in rows)
    duplicate_ids = sorted(
        candidate_id
        for candidate_id, count in candidate_counts.items()
        if candidate_id and count > 1
    )
    unknown_ids = sorted(
        candidate_id for candidate_id in candidate_counts if candidate_id not in expected
    )
    missing_ids = sorted(set(expected) - set(candidate_counts))
    invalid_values: list[dict[str, str]] = []
    altered_rows: list[dict[str, object]] = []
    incomplete_rows = 0
    selected_rows: list[dict[str, str]] = []
    reviewer_roles: Counter[str] = Counter()

    for row in rows:
        candidate_id = row.get("candidate_id", "")
        if candidate_id not in expected:
            continue
        altered_fields = [
            field for field, value in expected[candidate_id].items() if row.get(field, "") != value
        ]
        if altered_fields:
            altered_rows.append(
                {
                    "candidate_id": candidate_id,
                    "fields": altered_fields,
                }
            )
            continue
        judgments = [
            row.get("faithful", "").strip().lower(),
            row.get("central_checkable", "").strip().lower(),
            row.get("type_correct", "").strip().lower(),
            row.get("include_in_30", "").strip().lower(),
        ]
        for field, value in zip(
            (
                "faithful",
                "central_checkable",
                "type_correct",
                "include_in_30",
            ),
            judgments,
            strict=True,
        ):
            if value and value not in JUDGMENTS:
                invalid_values.append(
                    {"candidate_id": candidate_id, "field": field, "value": value}
                )
        reviewer_id = row.get("reviewer_id", "").strip()
        reviewer_role = row.get("reviewer_role", "").strip().lower()
        complete = (
            all(value in JUDGMENTS for value in judgments)
            and bool(reviewer_id)
            and reviewer_role in {"author", "independent"}
        )
        if not complete:
            incomplete_rows += 1
            continue
        reviewer_roles[reviewer_role] += 1
        if judgments[3] == "yes":
            category = row.get("primary_category", "").strip().lower()
            if category not in CATEGORIES:
                invalid_values.append(
                    {
                        "candidate_id": candidate_id,
                        "field": "primary_category",
                        "value": category,
                    }
                )
                continue
            if any(value != "yes" for value in judgments[:3]):
                invalid_values.append(
                    {
                        "candidate_id": candidate_id,
                        "field": "include_in_30",
                        "value": "Selected claims require three yes judgments.",
                    }
                )
                continue
            selected_rows.append(
                {
                    **row,
                    "case_id": expected[candidate_id]["case_id"],
                    "source_language": expected[candidate_id]["source_language"],
                    "primary_category": category,
                }
            )

    selected_by_language = Counter(row["source_language"] for row in selected_rows)
    selected_by_category = Counter(
        (row["source_language"], row["primary_category"]) for row in selected_rows
    )
    selected_by_case = Counter(row["case_id"] for row in selected_rows)
    blockers = []
    if duplicate_ids:
        blockers.append("Remove duplicate candidate rows.")
    if unknown_ids:
        blockers.append("Remove candidates that are not in the frozen pool.")
    if missing_ids:
        blockers.append("Restore every candidate from the frozen pool.")
    if altered_rows:
        blockers.append("Restore immutable candidate fields from the frozen pool.")
    if invalid_values:
        blockers.append("Fix invalid judgments, categories, or unsafe selections.")
    if incomplete_rows:
        completed_rows = len(rows) - incomplete_rows
        blockers.append(
            f"Complete all candidate reviews ({completed_rows}/{len(expected)} complete)."
        )
    if selected_by_language != Counter({"en": 10, "vi": 10, "ko": 10}):
        blockers.append("Select exactly 10 claims in each source language.")
    for language in sorted(LANGUAGES):
        category_counts = [
            selected_by_category[(language, category)] for category in sorted(CATEGORIES)
        ]
        if category_counts != [2, 2, 2, 2, 2]:
            blockers.append(
                f"Select exactly two {language.upper()} claims in each evaluation category."
            )
    manifest_cases = {case["id"] for case in pool["cases"]}
    uncovered_cases = sorted(
        case_id for case_id in manifest_cases if selected_by_case[case_id] == 0
    )
    if uncovered_cases:
        blockers.append("Select at least one claim from every source article.")

    return {
        "pool_complete": pool.get("complete") is True,
        "pool_candidates": len(expected),
        "reviewed_rows": len(rows) - incomplete_rows,
        "selected_claims": len(selected_rows),
        "selected_by_language": dict(sorted(selected_by_language.items())),
        "selected_by_language_and_category": {
            language: {
                category: selected_by_category[(language, category)]
                for category in sorted(CATEGORIES)
            }
            for language in sorted(LANGUAGES)
        },
        "selected_by_case": dict(sorted(selected_by_case.items())),
        "reviewer_roles": dict(sorted(reviewer_roles.items())),
        "duplicate_candidate_ids": duplicate_ids,
        "unknown_candidate_ids": unknown_ids,
        "missing_candidate_ids": missing_ids,
        "altered_rows": altered_rows,
        "invalid_values": invalid_values,
        "uncovered_cases": uncovered_cases,
        "ready_for_evidence_adjudication": not blockers,
        "blockers": blockers,
    }
