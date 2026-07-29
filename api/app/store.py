import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.models import (
    AnalysisJob,
    AnalysisResult,
    AnalysisStatus,
    ClaimCandidate,
    FactCheckFeedbackCreate,
    FactCheckFeedbackRecord,
    FactCheckJob,
    FactCheckResult,
    FactCheckStatus,
    FeedbackCreate,
    FeedbackRecord,
)


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL,
                    flag_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    correction TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                );

                CREATE TABLE IF NOT EXISTS analysis_cache (
                    cache_key TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fact_checks (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    candidates_json TEXT NOT NULL DEFAULT '[]',
                    selected_candidate_ids_json TEXT NOT NULL DEFAULT '[]',
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                );

                CREATE TABLE IF NOT EXISTS fact_check_feedback (
                    id TEXT PRIMARY KEY,
                    fact_check_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    correction TEXT,
                    better_source_url TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (fact_check_id, target_type, target_id),
                    FOREIGN KEY (fact_check_id) REFERENCES fact_checks(id)
                );
                """
            )
            feedback_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(feedback)").fetchall()
            }
            if "reviewer_role" not in feedback_columns:
                connection.execute(
                    """
                    ALTER TABLE feedback
                    ADD COLUMN reviewer_role TEXT NOT NULL DEFAULT 'unspecified'
                    """
                )
            fact_check_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(fact_checks)").fetchall()
            }
            if "result_json" not in fact_check_columns:
                connection.execute("ALTER TABLE fact_checks ADD COLUMN result_json TEXT")

    def create_analysis(self) -> AnalysisJob:
        job = AnalysisJob(
            id=str(uuid4()),
            status=AnalysisStatus.QUEUED,
            stage="Waiting to start",
            progress=0,
        )
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analyses (id, status, stage, progress, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job.id, job.status, job.stage, job.progress, now, now),
            )
        return job

    def update_analysis(
        self,
        analysis_id: str,
        *,
        status: AnalysisStatus,
        stage: str,
        progress: int,
        result: AnalysisResult | None = None,
        error: str | None = None,
    ) -> None:
        result_json = json.dumps(result.model_dump(mode="json")) if result else None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE analyses
                SET status = ?, stage = ?, progress = ?, result_json = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, stage, progress, result_json, error, _now(), analysis_id),
            )

    def get_analysis(self, analysis_id: str) -> AnalysisJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, status, stage, progress, result_json, error FROM analyses WHERE id = ?",
                (analysis_id,),
            ).fetchone()
        if row is None:
            return None
        result = (
            AnalysisResult.model_validate_json(row["result_json"]) if row["result_json"] else None
        )
        return AnalysisJob(
            id=row["id"],
            status=row["status"],
            stage=row["stage"],
            progress=row["progress"],
            result=result,
            error=row["error"],
        )

    def add_feedback(self, analysis_id: str, feedback: FeedbackCreate) -> FeedbackRecord:
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT id FROM feedback
                WHERE analysis_id = ? AND flag_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (analysis_id, feedback.flag_id),
            ).fetchone()
            record = FeedbackRecord(
                id=existing["id"] if existing else str(uuid4()),
                analysis_id=analysis_id,
                **feedback.model_dump(),
            )
            if existing:
                connection.execute(
                    """
                    UPDATE feedback
                    SET verdict = ?, correction = ?, reviewer_role = ?, created_at = ?
                    WHERE id = ?
                    """,
                    (
                        record.verdict,
                        record.correction,
                        record.reviewer_role,
                        _now(),
                        record.id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO feedback
                        (id, analysis_id, flag_id, verdict, correction, reviewer_role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.analysis_id,
                        record.flag_id,
                        record.verdict,
                        record.correction,
                        record.reviewer_role,
                        _now(),
                    ),
                )
        return record

    def get_cached_result(self, cache_key: str) -> AnalysisResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM analysis_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return AnalysisResult.model_validate_json(row["result_json"])

    def cache_result(self, cache_key: str, result: AnalysisResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO analysis_cache (cache_key, result_json, created_at)
                VALUES (?, ?, ?)
                """,
                (cache_key, json.dumps(result.model_dump(mode="json")), _now()),
            )

    def create_or_get_fact_check(self, analysis_id: str) -> tuple[FactCheckJob, bool]:
        existing = self.get_fact_check_for_analysis(analysis_id)
        if existing is not None:
            return existing, False

        job = FactCheckJob(
            id=str(uuid4()),
            analysis_id=analysis_id,
            status=FactCheckStatus.EXTRACTING_CLAIMS,
            stage="Finding checkable claims",
            progress=10,
        )
        now = _now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO fact_checks
                        (id, analysis_id, status, stage, progress, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.id,
                        analysis_id,
                        job.status,
                        job.stage,
                        job.progress,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError:
            concurrent = self.get_fact_check_for_analysis(analysis_id)
            if concurrent is None:
                raise
            return concurrent, False
        return job, True

    def update_fact_check(
        self,
        fact_check_id: str,
        *,
        status: FactCheckStatus,
        stage: str,
        progress: int,
        candidates: list[ClaimCandidate] | None = None,
        selected_candidate_ids: list[str] | None = None,
        result: FactCheckResult | None = None,
        error: str | None = None,
    ) -> None:
        assignments = ["status = ?", "stage = ?", "progress = ?", "error = ?", "updated_at = ?"]
        values: list[object] = [status, stage, progress, error, _now()]
        if candidates is not None:
            assignments.append("candidates_json = ?")
            values.append(
                json.dumps([candidate.model_dump(mode="json") for candidate in candidates])
            )
        if selected_candidate_ids is not None:
            assignments.append("selected_candidate_ids_json = ?")
            values.append(json.dumps(selected_candidate_ids))
        if result is not None:
            assignments.append("result_json = ?")
            values.append(json.dumps(result.model_dump(mode="json")))
        values.append(fact_check_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE fact_checks SET {', '.join(assignments)} WHERE id = ?",
                values,
            )

    def get_fact_check(self, fact_check_id: str) -> FactCheckJob | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, analysis_id, status, stage, progress, candidates_json,
                       selected_candidate_ids_json, result_json, error
                FROM fact_checks
                WHERE id = ?
                """,
                (fact_check_id,),
            ).fetchone()
        return _fact_check_from_row(row)

    def get_fact_check_for_analysis(self, analysis_id: str) -> FactCheckJob | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, analysis_id, status, stage, progress, candidates_json,
                       selected_candidate_ids_json, result_json, error
                FROM fact_checks
                WHERE analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()
        return _fact_check_from_row(row)

    def add_fact_check_feedback(
        self,
        fact_check_id: str,
        feedback: FactCheckFeedbackCreate,
    ) -> FactCheckFeedbackRecord:
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT id FROM fact_check_feedback
                WHERE fact_check_id = ? AND target_type = ? AND target_id = ?
                """,
                (fact_check_id, feedback.target_type, feedback.target_id),
            ).fetchone()
            record = FactCheckFeedbackRecord(
                id=existing["id"] if existing else str(uuid4()),
                fact_check_id=fact_check_id,
                **feedback.model_dump(),
            )
            values = (
                record.verdict,
                record.correction,
                str(record.better_source_url) if record.better_source_url else None,
                _now(),
            )
            if existing:
                connection.execute(
                    """
                    UPDATE fact_check_feedback
                    SET verdict = ?, correction = ?, better_source_url = ?, created_at = ?
                    WHERE id = ?
                    """,
                    (*values, record.id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO fact_check_feedback
                        (id, fact_check_id, target_type, target_id, verdict, correction,
                         better_source_url, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.fact_check_id,
                        record.target_type,
                        record.target_id,
                        *values,
                    ),
                )
        return record

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _fact_check_from_row(row: sqlite3.Row | None) -> FactCheckJob | None:
    if row is None:
        return None
    candidates = [
        ClaimCandidate.model_validate(item) for item in json.loads(row["candidates_json"])
    ]
    return FactCheckJob(
        id=row["id"],
        analysis_id=row["analysis_id"],
        status=row["status"],
        stage=row["stage"],
        progress=row["progress"],
        candidates=candidates,
        selected_candidate_ids=json.loads(row["selected_candidate_ids_json"]),
        result=(
            FactCheckResult.model_validate_json(row["result_json"]) if row["result_json"] else None
        ),
        error=row["error"],
    )
