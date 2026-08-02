import re
import sqlite3
from pathlib import Path

from app.models import AnalysisResult

ANALYSIS_LINK = re.compile(
    r"[?&]analysis=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def verify_demo_fallback(database: Path, reviewer_guide: Path) -> dict[str, object]:
    blockers: list[str] = []
    try:
        guide_text = reviewer_guide.read_text(encoding="utf-8")
    except OSError as error:
        guide_text = ""
        blockers.append(f"Could not read reviewer guide: {error}")
    analysis_ids = list(dict.fromkeys(ANALYSIS_LINK.findall(guide_text)))
    if not analysis_ids:
        blockers.append("The reviewer guide contains no analysis links.")

    integrity = "not_checked"
    rows: dict[str, sqlite3.Row] = {}
    if not database.is_file():
        blockers.append(f"Fallback database does not exist: {database}")
    else:
        uri = f"{database.resolve().as_uri()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    blockers.append(f"SQLite integrity check returned: {integrity}")
                if analysis_ids:
                    placeholders = ", ".join("?" for _ in analysis_ids)
                    result = connection.execute(
                        f"""
                        SELECT id, status, progress, result_json
                        FROM analyses
                        WHERE id IN ({placeholders})
                        """,
                        analysis_ids,
                    ).fetchall()
                    rows = {row["id"]: row for row in result}
        except sqlite3.Error as error:
            blockers.append(f"Could not read fallback database: {error}")

    ready_ids: list[str] = []
    for analysis_id in analysis_ids:
        row = rows.get(analysis_id)
        if row is None:
            blockers.append(f"Missing reviewer-guide analysis: {analysis_id}")
            continue
        if row["status"] != "complete" or row["progress"] != 100 or not row["result_json"]:
            blockers.append(f"Reviewer-guide analysis is not complete: {analysis_id}")
            continue
        try:
            analysis = AnalysisResult.model_validate_json(row["result_json"])
        except ValueError as error:
            blockers.append(
                f"Reviewer-guide analysis has an invalid result: {analysis_id}: {error}"
            )
            continue
        if not analysis.segments:
            blockers.append(f"Reviewer-guide analysis has no segments: {analysis_id}")
            continue
        if any(
            len(segment.translations) != 2
            or any(not translation.text.strip() for translation in segment.translations)
            for segment in analysis.segments
        ):
            blockers.append(
                f"Reviewer-guide analysis does not contain both complete target tabs: {analysis_id}"
            )
            continue
        ready_ids.append(analysis_id)

    return {
        "database": str(database),
        "reviewer_guide": str(reviewer_guide),
        "integrity": integrity,
        "expected_analyses": len(analysis_ids),
        "ready_analyses": len(ready_ids),
        "ready_analysis_ids": ready_ids,
        "blockers": blockers,
        "ready_for_translation_recording": bool(analysis_ids) and not blockers,
    }
