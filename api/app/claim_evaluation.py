import csv
import json
from collections import Counter
from pathlib import Path
from typing import TextIO

REVIEW_FIELDS = [
    "case_id",
    "source_language",
    "source_url",
    "candidate_rank",
    "candidate_id",
    "claim_type",
    "source_quote",
    "standalone_claim",
    "faithful",
    "central_checkable",
    "type_correct",
    "reviewer_id",
    "reviewer_role",
    "notes",
]
LABELS = {"yes", "no", "unsure"}


def write_claim_review_sheet(candidate_path: Path, output: TextIO) -> None:
    data = json.loads(candidate_path.read_text())
    writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
    writer.writeheader()
    for case in data["cases"]:
        for rank, candidate in enumerate(case["candidates"], start=1):
            writer.writerow(
                {
                    "case_id": case["id"],
                    "source_language": case["source_language"],
                    "source_url": case["url"],
                    "candidate_rank": rank,
                    "candidate_id": candidate["id"],
                    "claim_type": candidate["claim_type"],
                    "source_quote": candidate["source_quote"],
                    "standalone_claim": candidate["standalone_claim"],
                    "faithful": "",
                    "central_checkable": "",
                    "type_correct": "",
                    "reviewer_id": "",
                    "reviewer_role": "",
                    "notes": "",
                }
            )


def summarize_claim_reviews(
    candidate_path: Path,
    review_path: Path,
) -> dict[str, object]:
    candidates = json.loads(candidate_path.read_text())
    expected = {
        candidate["id"]: {
            "case_id": case["id"],
            "language": case["source_language"],
            "rank": rank,
        }
        for case in candidates["cases"]
        for rank, candidate in enumerate(case["candidates"], start=1)
    }
    with review_path.open(newline="") as source:
        rows = list(csv.DictReader(source))

    duplicate_ids = [
        candidate_id
        for candidate_id, count in Counter(row.get("candidate_id", "") for row in rows).items()
        if candidate_id and count > 1
    ]
    unknown_ids = sorted(
        {row.get("candidate_id", "") for row in rows if row.get("candidate_id", "") not in expected}
    )
    invalid_labels = []
    reviewed: dict[str, bool] = {}
    accepted: dict[str, bool] = {}
    reviewer_roles: Counter[str] = Counter()
    reviewer_ids: Counter[str] = Counter()
    missing_reviewer_identity = 0
    invalid_reviewer_roles: set[str] = set()
    for row in rows:
        candidate_id = row.get("candidate_id", "")
        labels = [
            row.get("faithful", "").strip().lower(),
            row.get("central_checkable", "").strip().lower(),
            row.get("type_correct", "").strip().lower(),
        ]
        for field, label in zip(
            ("faithful", "central_checkable", "type_correct"),
            labels,
            strict=True,
        ):
            if label and label not in LABELS:
                invalid_labels.append(
                    {"candidate_id": candidate_id, "field": field, "value": label}
                )
        is_reviewed = all(label in LABELS for label in labels)
        reviewed[candidate_id] = is_reviewed
        accepted[candidate_id] = is_reviewed and all(label == "yes" for label in labels)
        role = row.get("reviewer_role", "").strip().lower()
        reviewer_id = row.get("reviewer_id", "").strip()
        if is_reviewed:
            if role in {"author", "independent"}:
                reviewer_roles[role] += 1
            elif role:
                invalid_reviewer_roles.add(role)
            if reviewer_id:
                reviewer_ids[reviewer_id] += 1
            if not reviewer_id or not role:
                missing_reviewer_identity += 1

    cases = []
    language_success: dict[str, list[bool]] = {}
    for case in candidates["cases"]:
        case_ids = [candidate["id"] for candidate in case["candidates"]]
        top_three = case_ids[:3]
        fully_reviewed = all(reviewed.get(candidate_id, False) for candidate_id in case_ids)
        top_three_success = (
            any(accepted.get(candidate_id, False) for candidate_id in top_three)
            if all(reviewed.get(candidate_id, False) for candidate_id in top_three)
            else None
        )
        if top_three_success is not None:
            language_success.setdefault(case["source_language"], []).append(top_three_success)
        cases.append(
            {
                "case_id": case["id"],
                "source_language": case["source_language"],
                "candidate_count": len(case_ids),
                "reviewed_candidates": sum(
                    reviewed.get(candidate_id, False) for candidate_id in case_ids
                ),
                "fully_reviewed": fully_reviewed,
                "top_three_has_acceptable_candidate": top_three_success,
            }
        )

    reviewed_count = sum(reviewed.get(candidate_id, False) for candidate_id in expected)
    decided_cases = [
        case for case in cases if case["top_three_has_acceptable_candidate"] is not None
    ]
    successes = sum(case["top_three_has_acceptable_candidate"] is True for case in decided_cases)
    language_rates = {
        language: round(sum(values) / len(values), 3)
        for language, values in sorted(language_success.items())
        if values
    }
    blockers = []
    if duplicate_ids:
        blockers.append("Remove duplicate candidate rows before summarizing.")
    if unknown_ids:
        blockers.append("Remove rows that do not belong to the frozen candidate set.")
    if invalid_labels:
        blockers.append("Use only yes, no, or unsure in the three judgment columns.")
    if reviewed_count < len(expected):
        blockers.append(
            f"Review all frozen candidates ({reviewed_count}/{len(expected)} complete)."
        )
    if missing_reviewer_identity:
        blockers.append("Record a reviewer ID and role for every completed judgment.")
    if invalid_reviewer_roles:
        blockers.append("Use only author or independent as reviewer roles.")

    return {
        "candidate_artifact": str(candidate_path),
        "review_sheet": str(review_path),
        "candidate_count": len(expected),
        "reviewed_candidates": reviewed_count,
        "review_complete": not blockers and reviewed_count == len(expected),
        "top_three_success_rate": (
            round(successes / len(decided_cases), 3) if decided_cases else None
        ),
        "language_top_three_success_rate": language_rates,
        "reviewer_roles": dict(sorted(reviewer_roles.items())),
        "reviewer_ids": dict(sorted(reviewer_ids.items())),
        "cases": cases,
        "duplicate_candidate_ids": sorted(duplicate_ids),
        "unknown_candidate_ids": unknown_ids,
        "invalid_labels": invalid_labels,
        "invalid_reviewer_roles": sorted(invalid_reviewer_roles),
        "blockers": blockers,
    }
