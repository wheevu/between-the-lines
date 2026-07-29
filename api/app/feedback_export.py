import csv
import json
import sqlite3
from pathlib import Path
from typing import TextIO

from app.models import AnalysisResult, FactCheckResult

OVERALL_FEEDBACK_PREFIX = "__overall__:"


def write_feedback(database_path: Path, output: TextIO) -> None:
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "analysis_id",
            "scope",
            "source_language",
            "target_language",
            "kind",
            "category",
            "source_quote",
            "translation_quote",
            "verdict",
            "correction",
            "reviewer_role",
            "created_at",
        ],
    )
    writer.writeheader()
    if not database_path.exists():
        return

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    feedback_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(feedback)").fetchall()
    }
    reviewer_role = "f.reviewer_role" if "reviewer_role" in feedback_columns else "'unspecified'"
    rows = connection.execute(
        f"""
        SELECT f.analysis_id, f.flag_id, f.verdict, f.correction,
               {reviewer_role} AS reviewer_role, f.created_at,
               a.result_json
        FROM feedback AS f
        JOIN analyses AS a ON a.id = f.analysis_id
        ORDER BY f.created_at
        """
    ).fetchall()

    for row in rows:
        if not row["result_json"]:
            continue
        result = AnalysisResult.model_validate(json.loads(row["result_json"]))
        flag = next(
            (
                flag
                for segment in result.segments
                for translation in segment.translations
                for flag in translation.flags
                if flag.id == row["flag_id"]
            ),
            None,
        )
        is_overall = row["flag_id"].startswith(OVERALL_FEEDBACK_PREFIX)
        overall_target = row["flag_id"].removeprefix(OVERALL_FEEDBACK_PREFIX) if is_overall else ""
        if flag is None and not is_overall:
            continue
        writer.writerow(
            {
                "analysis_id": row["analysis_id"],
                "scope": "passage" if is_overall else "flag",
                "source_language": result.source_language.value,
                "target_language": overall_target if is_overall else flag.target_language.value,
                "kind": "" if is_overall else flag.kind.value,
                "category": "" if is_overall else flag.category.value,
                "source_quote": "" if is_overall else flag.source_quote,
                "translation_quote": "" if is_overall else flag.translation_quote,
                "verdict": row["verdict"],
                "correction": row["correction"],
                "reviewer_role": row["reviewer_role"],
                "created_at": row["created_at"],
            }
        )


def write_fact_check_feedback(database_path: Path, output: TextIO) -> None:
    fieldnames = [
        "fact_check_id",
        "target_type",
        "target_id",
        "claim_id",
        "claim_text",
        "status",
        "publisher",
        "evidence_url",
        "evidence_excerpt",
        "verdict",
        "correction",
        "better_source_url",
        "checked_at",
        "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    if not database_path.exists():
        return

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    table = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'fact_check_feedback'
        """
    ).fetchone()
    if table is None:
        return
    rows = connection.execute(
        """
        SELECT f.fact_check_id, f.target_type, f.target_id, f.verdict,
               f.correction, f.better_source_url, f.created_at, c.result_json
        FROM fact_check_feedback AS f
        JOIN fact_checks AS c ON c.id = f.fact_check_id
        ORDER BY f.created_at
        """
    ).fetchall()
    for row in rows:
        if not row["result_json"]:
            continue
        result = FactCheckResult.model_validate_json(row["result_json"])
        claim_result = next(
            (
                claim
                for claim in result.claims
                if claim.claim.id == row["target_id"]
                or any(item.id == row["target_id"] for item in claim.evidence)
            ),
            None,
        )
        if claim_result is None:
            continue
        evidence = next(
            (item for item in claim_result.evidence if item.id == row["target_id"]),
            None,
        )
        writer.writerow(
            {
                "fact_check_id": row["fact_check_id"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "claim_id": claim_result.claim.id,
                "claim_text": claim_result.claim.standalone_claim,
                "status": claim_result.assessment.status.value,
                "publisher": evidence.publisher if evidence else "",
                "evidence_url": evidence.url if evidence else "",
                "evidence_excerpt": evidence.excerpt if evidence else "",
                "verdict": row["verdict"],
                "correction": row["correction"],
                "better_source_url": row["better_source_url"],
                "checked_at": result.checked_at,
                "created_at": row["created_at"],
            }
        )
