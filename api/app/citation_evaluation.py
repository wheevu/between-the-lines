import csv
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import TextIO

from app.models import ClaimCheckResult
from app.system_evaluation import summarize_system_run

JUDGMENTS = {"yes", "no", "unsure"}
ROLES = {"author", "independent"}
IMMUTABLE_FIELDS = [
    "system_results_sha256",
    "candidate_id",
    "source_language",
    "standalone_claim",
    "evidence_rank",
    "evidence_id",
    "citation_role",
    "url",
    "publisher",
    "evidence_language",
    "excerpt",
    "system_stance",
    "stance_reason",
]
REVIEW_FIELDS = [
    "relevant_to_claim",
    "excerpt_matches_source",
    "stance_correct",
    "reviewer_id",
    "reviewer_role",
    "notes",
]
FIELDS = [*IMMUTABLE_FIELDS, *REVIEW_FIELDS]


def write_citation_review_sheet(
    adjudication_path: Path,
    selection_path: Path,
    results_path: Path,
    output: TextIO,
) -> None:
    summary = summarize_system_run(adjudication_path, selection_path, results_path)
    if not summary["ready_for_human_citation_review"]:
        raise ValueError("The frozen system run is not ready for citation review.")
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(_expected_rows(adjudication_path, results_path))


def summarize_citation_review(
    adjudication_path: Path,
    selection_path: Path,
    results_path: Path,
    review_path: Path,
) -> dict[str, object]:
    system_summary = summarize_system_run(adjudication_path, selection_path, results_path)
    expected_rows = _expected_rows(adjudication_path, results_path)
    expected_by_key = {_row_key(row): row for row in expected_rows}
    with review_path.open(newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    blockers = []
    if not system_summary["ready_for_human_citation_review"]:
        blockers.append("The frozen system run is not ready for citation review.")
    if fieldnames != FIELDS:
        blockers.append("Restore the citation-review columns in their original order.")

    row_counts = Counter(_row_key(row) for row in rows)
    duplicate_keys = sorted(key for key, count in row_counts.items() if count > 1)
    unknown_keys = sorted(set(row_counts) - set(expected_by_key))
    missing_keys = sorted(set(expected_by_key) - set(row_counts))
    if duplicate_keys:
        blockers.append("Remove duplicate citation rows.")
    if unknown_keys:
        blockers.append("Remove citations that are not in the frozen system run.")
    if missing_keys:
        blockers.append("Restore every cited passage from the frozen system run.")

    altered_rows = []
    invalid_values = []
    incomplete_rows = []
    reviewed_rows = []
    for row in rows:
        key = _row_key(row)
        expected = expected_by_key.get(key)
        if expected is None:
            continue
        altered_fields = [
            field for field in IMMUTABLE_FIELDS if row.get(field, "") != expected[field]
        ]
        if altered_fields:
            altered_rows.append(
                {
                    "candidate_id": key[0],
                    "evidence_id": key[1],
                    "fields": altered_fields,
                }
            )
            continue

        judgments = {field: row.get(field, "").strip().lower() for field in REVIEW_FIELDS[:3]}
        for field, value in judgments.items():
            if value and value not in JUDGMENTS:
                invalid_values.append(
                    {
                        "candidate_id": key[0],
                        "evidence_id": key[1],
                        "field": field,
                        "value": value,
                    }
                )
        reviewer_id = row.get("reviewer_id", "").strip()
        reviewer_role = row.get("reviewer_role", "").strip().lower()
        if reviewer_role and reviewer_role not in ROLES:
            invalid_values.append(
                {
                    "candidate_id": key[0],
                    "evidence_id": key[1],
                    "field": "reviewer_role",
                    "value": reviewer_role,
                }
            )
        if (
            not all(value in JUDGMENTS for value in judgments.values())
            or not reviewer_id
            or reviewer_role not in ROLES
        ):
            incomplete_rows.append(key)
            continue
        reviewed_rows.append(
            {
                **row,
                **judgments,
                "reviewer_role": reviewer_role,
                "citation_correct": all(value == "yes" for value in judgments.values()),
                "decided": all(value != "unsure" for value in judgments.values()),
            }
        )

    if altered_rows:
        blockers.append("Restore immutable citation data from the frozen system run.")
    if invalid_values:
        blockers.append("Use only yes, no, or unsure judgments and a valid reviewer role.")
    if incomplete_rows:
        blockers.append("Complete every citation judgment and reviewer field.")
    if len(rows) != len(expected_rows):
        blockers.append("Review exactly the citations referenced by the system assessment.")

    expected_count = len(expected_rows)
    if expected_count == 0:
        blockers.append("The system assessment cited no evidence to review.")
    reviewed_count = len(reviewed_rows)
    independent_count = sum(row["reviewer_role"] == "independent" for row in reviewed_rows)
    undecided_count = sum(not row["decided"] for row in reviewed_rows)
    structurally_complete = not blockers and reviewed_count == expected_count
    citation_correctness = (
        _rate(row["citation_correct"] for row in reviewed_rows) if structurally_complete else None
    )
    by_language = _by_language(expected_rows, reviewed_rows, valid=structurally_complete)
    language_rates = [
        item["citation_correctness"]
        for item in by_language.values()
        if item["citation_correctness"] is not None
    ]
    language_gap = (
        round(max(language_rates) - min(language_rates), 3) if len(language_rates) == 3 else None
    )
    citation_gate_passed = (
        structurally_complete
        and independent_count == expected_count
        and undecided_count == 0
        and citation_correctness is not None
        and citation_correctness >= 0.9
    )
    return {
        "expected_citations": expected_count,
        "reviewed_citations": reviewed_count,
        "independent_citations": independent_count,
        "undecided_citations": undecided_count,
        "citation_correctness": citation_correctness,
        "citation_correctness_by_source_language": by_language,
        "largest_language_gap": language_gap,
        "reviewer_roles": dict(
            sorted(Counter(row["reviewer_role"] for row in reviewed_rows).items())
        ),
        "counterexamples": [
            {
                "candidate_id": row["candidate_id"],
                "evidence_id": row["evidence_id"],
                "relevant_to_claim": row["relevant_to_claim"],
                "excerpt_matches_source": row["excerpt_matches_source"],
                "stance_correct": row["stance_correct"],
                "notes": row.get("notes", ""),
            }
            for row in reviewed_rows
            if not row["citation_correct"]
        ],
        "duplicate_citations": [
            {"candidate_id": key[0], "evidence_id": key[1]} for key in duplicate_keys
        ],
        "unknown_citations": [
            {"candidate_id": key[0], "evidence_id": key[1]} for key in unknown_keys
        ],
        "missing_citations": [
            {"candidate_id": key[0], "evidence_id": key[1]} for key in missing_keys
        ],
        "altered_rows": altered_rows,
        "invalid_values": invalid_values,
        "ready_for_reporting": structurally_complete,
        "citation_gate_passed": citation_gate_passed,
        "blockers": list(dict.fromkeys(blockers)),
        "note": (
            "The ≥90% gate applies only when every cited passage has a decided, "
            "independent review. Unsure judgments and author-only review never pass it."
        ),
    }


def _expected_rows(adjudication_path: Path, results_path: Path) -> list[dict[str, str]]:
    adjudication = json.loads(adjudication_path.read_text())
    languages = {
        claim["candidate_id"]: claim["source_language"] for claim in adjudication.get("claims", [])
    }
    results_hash = sha256(results_path.read_bytes()).hexdigest()
    results = json.loads(results_path.read_text())
    rows = []
    for raw in results.get("claims", []):
        result = ClaimCheckResult.model_validate(raw)
        role_by_id = {
            **{item_id: "supports" for item_id in result.assessment.support_evidence_ids},
            **{item_id: "disputes" for item_id in result.assessment.challenge_evidence_ids},
            **{item_id: "context" for item_id in result.assessment.context_evidence_ids},
        }
        for rank, evidence in enumerate(result.evidence, start=1):
            role = role_by_id.get(evidence.id)
            if role is None:
                continue
            rows.append(
                {
                    "system_results_sha256": results_hash,
                    "candidate_id": result.claim.id,
                    "source_language": languages[result.claim.id],
                    "standalone_claim": result.claim.standalone_claim,
                    "evidence_rank": str(rank),
                    "evidence_id": evidence.id,
                    "citation_role": role,
                    "url": evidence.url,
                    "publisher": evidence.publisher,
                    "evidence_language": evidence.language.value,
                    "excerpt": evidence.excerpt,
                    "system_stance": evidence.stance.value if evidence.stance else "",
                    "stance_reason": evidence.stance_reason or "",
                    "relevant_to_claim": "",
                    "excerpt_matches_source": "",
                    "stance_correct": "",
                    "reviewer_id": "",
                    "reviewer_role": "",
                    "notes": "",
                }
            )
    return rows


def _row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("candidate_id", ""), row.get("evidence_id", "")


def _by_language(
    expected_rows: list[dict[str, str]],
    reviewed_rows: list[dict[str, object]],
    *,
    valid: bool,
) -> dict[str, dict[str, object]]:
    result = {}
    for language in ("en", "vi", "ko"):
        expected = [row for row in expected_rows if row["source_language"] == language]
        reviewed = [row for row in reviewed_rows if row["source_language"] == language]
        complete = len(expected) > 0 and len(reviewed) == len(expected)
        result[language] = {
            "expected": len(expected),
            "reviewed": len(reviewed),
            "citation_correctness": (
                _rate(row["citation_correct"] for row in reviewed) if valid and complete else None
            ),
        }
    return result


def _rate(values) -> float:
    collected = list(values)
    return round(sum(bool(value) for value in collected) / len(collected), 3)
