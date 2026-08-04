import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.models import (
    AnalysisJob,
    AnalysisResult,
    AnalysisStatus,
    ArticleEdition,
    ArticleEditionCreate,
    ArticleExport,
    ArticleLedger,
    ClaimCandidate,
    ClaimLedgerEntry,
    ClaimLedgerEntryCreate,
    EditionDiff,
    EditionSignals,
    EvidenceLink,
    EvidenceLinkRelation,
    FactCheckFeedbackCreate,
    FactCheckFeedbackRecord,
    FactCheckJob,
    FactCheckResult,
    FactCheckStatus,
    FeedbackCreate,
    FeedbackRecord,
    LedgerStatus,
    ReviewDecision,
    ReviewDecisionCreate,
    RevisionEvent,
    RevisionEventType,
    SourceSnapshot,
    SourceSnapshotCreate,
    SourceSnapshotStatus,
    TranslationCheck,
    TranslationCheckCreate,
    TranslationCheckStatus,
)
from app.provenance import (
    bounded_excerpt,
    canonicalize_url,
    diff_signals,
    extract_signals,
    normalized_claim_hash,
    payload_hash,
    text_hash,
    validate_sha256,
)

SCHEMA_VERSION = 2

_REQUIRED_LEDGER_COLUMNS = {
    "article_editions": {
        "id",
        "article_id",
        "version",
        "title",
        "source_language",
        "source_url",
        "source_sha256",
        "source_excerpt",
        "source_excerpt_sha256",
        "source_excerpt_start",
        "source_excerpt_end",
        "source_status",
        "signals_json",
        "created_at",
        "supersedes_edition_id",
        "revision_reason",
    },
    "source_snapshots": {
        "id",
        "edition_id",
        "url",
        "canonical_url",
        "title",
        "excerpt",
        "excerpt_sha256",
        "source_sha256",
        "start_offset",
        "end_offset",
        "status",
        "duplicate_of_id",
        "captured_at",
    },
    "claim_ledger_entries": {
        "id",
        "edition_id",
        "claim_text",
        "claim_hash",
        "start_offset",
        "end_offset",
        "segment_id",
        "status",
        "created_at",
        "updated_at",
    },
    "evidence_links": {
        "id",
        "claim_id",
        "snapshot_id",
        "quote",
        "quote_sha256",
        "start_offset",
        "end_offset",
        "relation",
        "created_at",
    },
    "translation_checks": {
        "id",
        "claim_id",
        "edition_id",
        "target_language",
        "translation_text",
        "translation_sha256",
        "source_claim_hash",
        "status",
        "notes",
        "created_at",
    },
    "review_decisions": {
        "id",
        "claim_id",
        "edition_id",
        "claim_hash",
        "status",
        "reviewer",
        "rationale",
        "decided_at",
    },
    "revision_events": {
        "id",
        "article_id",
        "edition_id",
        "event_type",
        "summary",
        "payload_hash",
        "created_at",
    },
}


class LedgerNotFoundError(LookupError):
    pass


class LedgerHashMismatchError(ValueError):
    pass


def _validate_span(
    label: str,
    start: int,
    end: int,
    *,
    limit: int | None = None,
) -> None:
    if start < 0 or end < start:
        raise ValueError(f"The {label} span must satisfy 0 <= start_offset <= end_offset.")
    if limit is not None and end > limit:
        raise ValueError(f"The {label} span extends beyond the supplied source text.")


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
            self._migrate_ledger(connection)

    @staticmethod
    def _migrate_ledger(connection: sqlite3.Connection) -> None:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version >= SCHEMA_VERSION:
            Store._verify_ledger_schema(connection)
            return
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS article_editions (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                title TEXT,
                source_language TEXT NOT NULL,
                source_url TEXT,
                source_sha256 TEXT NOT NULL,
                source_excerpt TEXT NOT NULL,
                source_excerpt_sha256 TEXT NOT NULL,
                source_excerpt_start INTEGER NOT NULL,
                source_excerpt_end INTEGER NOT NULL,
                source_status TEXT NOT NULL,
                signals_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                supersedes_edition_id TEXT,
                revision_reason TEXT,
                UNIQUE (article_id, version)
            );

            CREATE TABLE IF NOT EXISTS source_snapshots (
                id TEXT PRIMARY KEY,
                edition_id TEXT NOT NULL,
                url TEXT,
                canonical_url TEXT,
                title TEXT,
                excerpt TEXT NOT NULL,
                excerpt_sha256 TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                status TEXT NOT NULL,
                duplicate_of_id TEXT,
                captured_at TEXT NOT NULL,
                FOREIGN KEY (edition_id) REFERENCES article_editions(id)
            );

            CREATE TABLE IF NOT EXISTS claim_ledger_entries (
                id TEXT PRIMARY KEY,
                edition_id TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                claim_hash TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                segment_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (edition_id) REFERENCES article_editions(id)
            );

            CREATE TABLE IF NOT EXISTS evidence_links (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                quote TEXT NOT NULL,
                quote_sha256 TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                relation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES claim_ledger_entries(id),
                FOREIGN KEY (snapshot_id) REFERENCES source_snapshots(id)
            );

            CREATE TABLE IF NOT EXISTS translation_checks (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                edition_id TEXT NOT NULL,
                target_language TEXT NOT NULL,
                translation_text TEXT NOT NULL,
                translation_sha256 TEXT NOT NULL,
                source_claim_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES claim_ledger_entries(id),
                FOREIGN KEY (edition_id) REFERENCES article_editions(id)
            );

            CREATE TABLE IF NOT EXISTS review_decisions (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                edition_id TEXT NOT NULL,
                claim_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                rationale TEXT,
                decided_at TEXT NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES claim_ledger_entries(id),
                FOREIGN KEY (edition_id) REFERENCES article_editions(id)
            );

            CREATE TABLE IF NOT EXISTS revision_events (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                edition_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (edition_id) REFERENCES article_editions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_article_editions_article
                ON article_editions(article_id, version);
            CREATE INDEX IF NOT EXISTS idx_source_snapshots_edition
                ON source_snapshots(edition_id);
            CREATE INDEX IF NOT EXISTS idx_claim_ledger_entries_edition
                ON claim_ledger_entries(edition_id, start_offset);
            CREATE INDEX IF NOT EXISTS idx_evidence_links_claim
                ON evidence_links(claim_id);
            CREATE INDEX IF NOT EXISTS idx_translation_checks_claim
                ON translation_checks(claim_id);
            CREATE INDEX IF NOT EXISTS idx_review_decisions_claim
                ON review_decisions(claim_id, decided_at);
            CREATE INDEX IF NOT EXISTS idx_revision_events_article
                ON revision_events(article_id, created_at);
            """
        )
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        Store._verify_ledger_schema(connection)

    @staticmethod
    def _verify_ledger_schema(connection: sqlite3.Connection) -> None:
        """Fail closed when a database lies about its ledger schema version."""

        for table, required_columns in _REQUIRED_LEDGER_COLUMNS.items():
            rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
            actual_columns = {row["name"] for row in rows}
            missing = sorted(required_columns - actual_columns)
            if not rows:
                raise sqlite3.DatabaseError(
                    f"Ledger schema version {SCHEMA_VERSION} is missing table {table!r}."
                )
            if missing:
                missing_columns = ", ".join(missing)
                raise sqlite3.DatabaseError(
                    f"Ledger schema version {SCHEMA_VERSION} is missing columns in "
                    f"{table!r}: {missing_columns}."
                )

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

    def create_article_edition(
        self,
        article_id: str,
        request: ArticleEditionCreate,
    ) -> ArticleEdition:
        source_text = request.source_text
        # A source hash may describe private material that the caller deliberately
        # does not persist. Only verify it when the complete source text is present;
        # an excerpt has its own independently computed hash below.
        computed_source_hash = text_hash(source_text) if source_text is not None else None
        supplied_source_hash = (
            validate_sha256(request.source_sha256, field_name="source_sha256")
            if request.source_sha256
            else None
        )
        if (
            supplied_source_hash is not None
            and computed_source_hash is not None
            and supplied_source_hash != computed_source_hash
        ):
            raise ValueError(
                "The supplied source hash does not match the supplied source material."
            )
        source_hash = supplied_source_hash or computed_source_hash
        if source_hash is None and request.source_snapshots:
            first_snapshot = request.source_snapshots[0]
            if first_snapshot.source_sha256:
                source_hash = validate_sha256(
                    first_snapshot.source_sha256,
                    field_name="source_snapshots.source_sha256",
                )
            elif first_snapshot.excerpt:
                source_hash = text_hash(first_snapshot.excerpt)
        source_hash = source_hash or text_hash(request.source_excerpt or "")
        excerpt = (
            request.source_excerpt
            if request.source_excerpt is not None
            else bounded_excerpt(source_text or "")
        )
        excerpt_start = request.source_excerpt_start
        excerpt_end = excerpt_start + len(excerpt)
        _validate_span(
            "source excerpt",
            excerpt_start,
            excerpt_end,
            limit=len(source_text) if source_text is not None else None,
        )
        if source_text is not None and source_text[excerpt_start:excerpt_end] != excerpt:
            raise ValueError("The source excerpt does not match its declared source span.")
        signals = extract_signals(excerpt)
        now = _now()
        edition_id = str(uuid4())

        with self._connect() as connection:
            latest = connection.execute(
                "SELECT MAX(version) AS version FROM article_editions WHERE article_id = ?",
                (article_id,),
            ).fetchone()
            version = (latest["version"] or 0) + 1
            if request.supersedes_edition_id:
                superseded = connection.execute(
                    """
                    SELECT id FROM article_editions
                    WHERE id = ? AND article_id = ?
                    """,
                    (request.supersedes_edition_id, article_id),
                ).fetchone()
                if superseded is None:
                    raise ValueError("The superseded edition belongs to another article.")

            connection.execute(
                """
                INSERT INTO article_editions
                    (id, article_id, version, title, source_language, source_url,
                     source_sha256, source_excerpt, source_excerpt_sha256,
                     source_excerpt_start, source_excerpt_end, source_status,
                     signals_json, created_at, supersedes_edition_id, revision_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edition_id,
                    article_id,
                    version,
                    request.title,
                    request.source_language,
                    str(request.source_url) if request.source_url else None,
                    source_hash,
                    excerpt,
                    text_hash(excerpt),
                    excerpt_start,
                    excerpt_end,
                    request.source_status,
                    json.dumps(signals.model_dump(mode="json"), ensure_ascii=False),
                    now,
                    request.supersedes_edition_id,
                    request.revision_reason,
                ),
            )

            using_default_snapshot = not request.source_snapshots
            snapshots = request.source_snapshots or [
                SourceSnapshotCreate(
                    url=request.source_url,
                    title=request.title,
                    excerpt=excerpt,
                    source_sha256=source_hash,
                    start_offset=excerpt_start,
                    end_offset=excerpt_end,
                    status=request.source_status,
                )
            ]
            article_source_url = canonicalize_url(
                str(request.source_url) if request.source_url else None
            )
            snapshot_bindings: list[tuple[str, str, int, int]] = []
            for snapshot_spec in snapshots:
                snapshot_url = str(snapshot_spec.url) if snapshot_spec.url else None
                canonical_url = canonicalize_url(snapshot_url)
                duplicate_of_id = None
                status = snapshot_spec.status
                snapshot_excerpt = snapshot_spec.excerpt or excerpt
                snapshot_start = snapshot_spec.start_offset
                snapshot_end = snapshot_spec.end_offset
                if snapshot_end is None:
                    snapshot_end = snapshot_start + len(snapshot_excerpt)
                is_article_source = using_default_snapshot or (
                    article_source_url is not None and canonical_url == article_source_url
                )
                _validate_span(
                    "source snapshot",
                    snapshot_start,
                    snapshot_end,
                    limit=len(source_text)
                    if source_text is not None and is_article_source
                    else None,
                )
                if snapshot_end - snapshot_start != len(snapshot_excerpt):
                    raise ValueError(
                        "The source snapshot span length must match its stored excerpt."
                    )
                if (
                    source_text is not None
                    and is_article_source
                    and source_text[snapshot_start:snapshot_end] != snapshot_excerpt
                ):
                    raise ValueError("The source snapshot does not match its declared source span.")
                supplied_snapshot_hash = (
                    validate_sha256(
                        snapshot_spec.source_sha256,
                        field_name="source_snapshots.source_sha256",
                    )
                    if snapshot_spec.source_sha256
                    else None
                )
                if (
                    supplied_snapshot_hash is not None
                    and is_article_source
                    and computed_source_hash is not None
                    and supplied_snapshot_hash != computed_source_hash
                ):
                    raise ValueError(
                        "The supplied source snapshot hash does not match the source material."
                    )
                snapshot_source_hash = supplied_snapshot_hash or (
                    source_hash if is_article_source else text_hash(snapshot_excerpt)
                )
                if canonical_url is not None and status is SourceSnapshotStatus.AVAILABLE:
                    previous_snapshots = connection.execute(
                        """
                        SELECT source_snapshots.id, source_snapshots.source_sha256
                        FROM source_snapshots
                        JOIN article_editions ON article_editions.id = source_snapshots.edition_id
                        WHERE article_editions.article_id = ?
                          AND source_snapshots.canonical_url = ?
                        ORDER BY article_editions.version DESC
                        """,
                        (article_id, canonical_url),
                    ).fetchall()
                    if previous_snapshots:
                        duplicate = next(
                            (
                                previous
                                for previous in previous_snapshots
                                if previous["source_sha256"] == snapshot_source_hash
                            ),
                            None,
                        )
                        if duplicate is not None:
                            duplicate_of_id = duplicate["id"]
                            status = SourceSnapshotStatus.DUPLICATE
                        else:
                            status = SourceSnapshotStatus.CHANGED
                snapshot_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO source_snapshots
                        (id, edition_id, url, canonical_url, title, excerpt,
                         excerpt_sha256, source_sha256, start_offset, end_offset,
                         status, duplicate_of_id, captured_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        edition_id,
                        snapshot_url,
                        canonical_url,
                        snapshot_spec.title,
                        snapshot_excerpt,
                        text_hash(snapshot_excerpt),
                        snapshot_source_hash,
                        snapshot_start,
                        snapshot_end,
                        status,
                        duplicate_of_id,
                        now,
                    ),
                )
                snapshot_bindings.append(
                    (snapshot_id, snapshot_excerpt, snapshot_start, snapshot_end)
                )

            claims = request.claims
            if not claims and excerpt:
                claims = [
                    # Keep the automatically seeded ledger useful without
                    # persisting the full article body.
                    ClaimLedgerEntryCreate(
                        text=excerpt,
                        start_offset=excerpt_start,
                        end_offset=excerpt_end,
                    )
                ]
            for claim_spec in claims:
                claim_start = claim_spec.start_offset
                claim_end = claim_spec.end_offset
                if claim_end is None:
                    claim_end = claim_start + len(claim_spec.text)
                _validate_span(
                    "claim",
                    claim_start,
                    claim_end,
                    limit=len(source_text) if source_text is not None else None,
                )
                matching_snapshots = [
                    (snapshot_id, snapshot_excerpt, snapshot_start)
                    for snapshot_id, snapshot_excerpt, snapshot_start, snapshot_end
                    in snapshot_bindings
                    if snapshot_start <= claim_start
                    and claim_end <= snapshot_end
                    and snapshot_excerpt[
                        claim_start - snapshot_start : claim_end - snapshot_start
                    ]
                    == claim_spec.text
                ]
                if source_text is not None:
                    if source_text[claim_start:claim_end] != claim_spec.text:
                        raise ValueError(
                            "The claim text does not match its declared source span."
                        )
                elif not matching_snapshots:
                    raise ValueError(
                        "The claim text and offsets must match a stored source snapshot."
                    )
                claim_id = str(uuid4())
                claim_hash = normalized_claim_hash(claim_spec.text)
                connection.execute(
                    """
                    INSERT INTO claim_ledger_entries
                        (id, edition_id, claim_text, claim_hash, start_offset,
                         end_offset, segment_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        edition_id,
                        bounded_excerpt(claim_spec.text),
                        claim_hash,
                        claim_start,
                        claim_end,
                        claim_spec.segment_id,
                        LedgerStatus.UNREVIEWED,
                        now,
                        now,
                    ),
                )
                for snapshot_id, snapshot_excerpt, snapshot_start in matching_snapshots:
                    quote = snapshot_excerpt[
                        claim_start - snapshot_start : claim_end - snapshot_start
                    ]
                    connection.execute(
                        """
                        INSERT INTO evidence_links
                            (id, claim_id, snapshot_id, quote, quote_sha256,
                             start_offset, end_offset, relation, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            claim_id,
                            snapshot_id,
                            quote,
                            text_hash(quote),
                            claim_start,
                            claim_end,
                            EvidenceLinkRelation.CONTEXT,
                            now,
                        ),
                    )
                for translation in claim_spec.translation_checks:
                    supplied_claim_hash = (
                        validate_sha256(
                            translation.source_claim_hash,
                            field_name="translation source_claim_hash",
                        )
                        if translation.source_claim_hash
                        else None
                    )
                    if supplied_claim_hash is not None and supplied_claim_hash != claim_hash:
                        raise ValueError(
                            "A translation check must reference the hash of its claim."
                        )
                    connection.execute(
                        """
                        INSERT INTO translation_checks
                            (id, claim_id, edition_id, target_language,
                             translation_text, translation_sha256, source_claim_hash,
                             status, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            claim_id,
                            edition_id,
                            translation.target_language,
                            bounded_excerpt(translation.translation_text),
                            text_hash(translation.translation_text),
                            claim_hash,
                            translation.status,
                            translation.notes,
                            now,
                        ),
                    )

            connection.execute(
                """
                INSERT INTO revision_events
                    (id, article_id, edition_id, event_type, summary, payload_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    article_id,
                    edition_id,
                    RevisionEventType.CREATED,
                    f"Edition {version} captured",
                    payload_hash(article_id, edition_id, source_hash, excerpt),
                    now,
                ),
            )
        created = self.get_article_edition(edition_id)
        if created is None:
            raise LedgerNotFoundError("The edition was created but could not be loaded.")
        return created

    def get_article_edition(self, edition_id: str) -> ArticleEdition | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM article_editions WHERE id = ?",
                (edition_id,),
            ).fetchone()
            return self._edition_from_row(connection, row)

    def get_article_ledger(self, article_id: str) -> ArticleLedger:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM article_editions
                WHERE article_id = ?
                ORDER BY version ASC
                """,
                (article_id,),
            ).fetchall()
            editions = [self._edition_from_row(connection, row) for row in rows]
        loaded_editions = [edition for edition in editions if edition is not None]
        return ArticleLedger(
            article_id=article_id,
            latest_edition_id=loaded_editions[-1].id if loaded_editions else None,
            editions=loaded_editions,
        )

    def ensure_article_ledger(self, article_id: str) -> ArticleLedger | None:
        ledger = self.get_article_ledger(article_id)
        if ledger.editions:
            return ledger
        analysis = self.get_analysis(article_id)
        if analysis is None or analysis.result is None:
            return None

        source_parts: list[str] = []
        claims: list[ClaimLedgerEntryCreate] = []
        offset = 0
        for index, segment in enumerate(analysis.result.segments):
            if index:
                source_parts.append("\n\n")
                offset += 2
            source_parts.append(segment.source_text)
            start = offset
            offset += len(segment.source_text)
            translation_checks = [
                TranslationCheckCreate(
                    target_language=translation.language,
                    translation_text=translation.text,
                    status=TranslationCheckStatus.UNCHECKED,
                )
                for translation in segment.translations
            ]
            claims.append(
                ClaimLedgerEntryCreate(
                    text=segment.source_text,
                    start_offset=start,
                    end_offset=offset,
                    segment_id=segment.id,
                    translation_checks=translation_checks,
                )
            )
        source_text = "".join(source_parts)
        created = self.create_article_edition(
            article_id,
            ArticleEditionCreate(
                title=analysis.result.source_title,
                source_language=analysis.result.source_language,
                source_url=analysis.result.source_url,
                source_text=source_text,
                claims=claims,
            ),
        )
        return ArticleLedger(
            article_id=article_id,
            latest_edition_id=created.id,
            editions=[created],
        )

    def get_edition_diff(
        self,
        edition_id: str,
        against_edition_id: str | None = None,
    ) -> EditionDiff:
        edition = self.get_article_edition(edition_id)
        if edition is None:
            raise LedgerNotFoundError("Edition not found.")
        if against_edition_id is None:
            ledger = self.get_article_ledger(edition.article_id)
            previous = [item for item in ledger.editions if item.version < edition.version]
            if not previous:
                raise ValueError("This article has no earlier edition to compare.")
            against_edition_id = previous[-1].id
        against = self.get_article_edition(against_edition_id)
        if against is None:
            raise LedgerNotFoundError("Comparison edition not found.")
        if against.article_id != edition.article_id:
            raise ValueError("Editions from different articles cannot be compared.")
        changes = diff_signals(against.signals, edition.signals)
        return EditionDiff(
            from_edition_id=edition.id,
            against_edition_id=against.id,
            article_id=edition.article_id,
            changed=edition.source_sha256 != against.source_sha256 or bool(changes),
            from_source_sha256=edition.source_sha256,
            against_source_sha256=against.source_sha256,
            changes=changes,
        )

    def review_claim(
        self,
        claim_id: str,
        review: ReviewDecisionCreate,
    ) -> ReviewDecision:
        now = _now()
        decision_id = str(uuid4())
        with self._connect() as connection:
            claim = connection.execute(
                "SELECT * FROM claim_ledger_entries WHERE id = ?",
                (claim_id,),
            ).fetchone()
            if claim is None:
                raise LedgerNotFoundError("Claim not found.")
            if claim["edition_id"] != review.edition_id:
                raise LedgerHashMismatchError("The claim belongs to another edition.")
            if claim["claim_hash"] != review.claim_hash:
                raise LedgerHashMismatchError(
                    "This claim changed since it was opened. Reload the edition before reviewing."
                )
            connection.execute(
                """
                INSERT INTO review_decisions
                    (id, claim_id, edition_id, claim_hash, status, reviewer, rationale, decided_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    claim_id,
                    review.edition_id,
                    review.claim_hash,
                    review.status,
                    review.reviewer,
                    review.rationale,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE claim_ledger_entries
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (review.status, now, claim_id),
            )
            connection.execute(
                """
                INSERT INTO revision_events
                    (id, article_id, edition_id, event_type, summary, payload_hash, created_at)
                SELECT ?, article_id, id, ?, ?, ?, ?
                FROM article_editions
                WHERE id = ?
                """,
                (
                    str(uuid4()),
                    RevisionEventType.CLAIM_REVIEWED,
                    f"Claim marked {review.status}",
                    payload_hash(claim_id, review.edition_id, review.claim_hash, review.status),
                    now,
                    review.edition_id,
                ),
            )
        return ReviewDecision(
            id=decision_id,
            claim_id=claim_id,
            edition_id=review.edition_id,
            claim_hash=review.claim_hash,
            status=review.status,
            reviewer=review.reviewer,
            rationale=review.rationale,
            decided_at=now,
        )

    def export_article(self, article_id: str) -> ArticleExport:
        return ArticleExport(
            article_id=article_id,
            exported_at=_now(),
            ledger=self.get_article_ledger(article_id),
        )

    @staticmethod
    def _edition_from_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row | None,
    ) -> ArticleEdition | None:
        if row is None:
            return None
        edition_id = row["id"]
        snapshot_rows = connection.execute(
            """
            SELECT * FROM source_snapshots
            WHERE edition_id = ?
            ORDER BY captured_at ASC, id ASC
            """,
            (edition_id,),
        ).fetchall()
        snapshots = [
            SourceSnapshot(
                id=item["id"],
                edition_id=item["edition_id"],
                url=item["url"],
                canonical_url=item["canonical_url"],
                title=item["title"],
                excerpt=item["excerpt"],
                excerpt_sha256=item["excerpt_sha256"],
                source_sha256=item["source_sha256"],
                start_offset=item["start_offset"],
                end_offset=item["end_offset"],
                status=item["status"],
                duplicate_of_id=item["duplicate_of_id"],
                captured_at=item["captured_at"],
            )
            for item in snapshot_rows
        ]
        claim_rows = connection.execute(
            """
            SELECT * FROM claim_ledger_entries
            WHERE edition_id = ?
            ORDER BY start_offset ASC, id ASC
            """,
            (edition_id,),
        ).fetchall()
        claims: list[ClaimLedgerEntry] = []
        for claim in claim_rows:
            claim_id = claim["id"]
            evidence_rows = connection.execute(
                "SELECT * FROM evidence_links WHERE claim_id = ? ORDER BY created_at, id",
                (claim_id,),
            ).fetchall()
            evidence_links = [
                EvidenceLink(
                    id=item["id"],
                    claim_id=item["claim_id"],
                    snapshot_id=item["snapshot_id"],
                    quote=item["quote"],
                    quote_sha256=item["quote_sha256"],
                    start_offset=item["start_offset"],
                    end_offset=item["end_offset"],
                    relation=item["relation"],
                    created_at=item["created_at"],
                )
                for item in evidence_rows
            ]
            translation_rows = connection.execute(
                "SELECT * FROM translation_checks WHERE claim_id = ? ORDER BY created_at, id",
                (claim_id,),
            ).fetchall()
            translation_checks = [
                TranslationCheck(
                    id=item["id"],
                    claim_id=item["claim_id"],
                    edition_id=item["edition_id"],
                    target_language=item["target_language"],
                    translation_text=item["translation_text"],
                    translation_sha256=item["translation_sha256"],
                    source_claim_hash=item["source_claim_hash"],
                    status=item["status"],
                    notes=item["notes"],
                    created_at=item["created_at"],
                )
                for item in translation_rows
            ]
            decision_rows = connection.execute(
                """
                SELECT * FROM review_decisions
                WHERE claim_id = ?
                ORDER BY decided_at ASC, id ASC
                """,
                (claim_id,),
            ).fetchall()
            review_decisions = [
                ReviewDecision(
                    id=item["id"],
                    claim_id=item["claim_id"],
                    edition_id=item["edition_id"],
                    claim_hash=item["claim_hash"],
                    status=item["status"],
                    reviewer=item["reviewer"],
                    rationale=item["rationale"],
                    decided_at=item["decided_at"],
                )
                for item in decision_rows
            ]
            claims.append(
                ClaimLedgerEntry(
                    id=claim_id,
                    edition_id=claim["edition_id"],
                    text=claim["claim_text"],
                    claim_hash=claim["claim_hash"],
                    start_offset=claim["start_offset"],
                    end_offset=claim["end_offset"],
                    segment_id=claim["segment_id"],
                    status=claim["status"],
                    created_at=claim["created_at"],
                    updated_at=claim["updated_at"],
                    evidence_links=evidence_links,
                    translation_checks=translation_checks,
                    review_decisions=review_decisions,
                )
            )
        event_rows = connection.execute(
            """
            SELECT * FROM revision_events
            WHERE edition_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (edition_id,),
        ).fetchall()
        events = [
            RevisionEvent(
                id=item["id"],
                article_id=item["article_id"],
                edition_id=item["edition_id"],
                event_type=item["event_type"],
                summary=item["summary"],
                payload_hash=item["payload_hash"],
                created_at=item["created_at"],
            )
            for item in event_rows
        ]
        return ArticleEdition(
            id=edition_id,
            article_id=row["article_id"],
            version=row["version"],
            title=row["title"],
            source_language=row["source_language"],
            source_url=row["source_url"],
            source_sha256=row["source_sha256"],
            source_excerpt=row["source_excerpt"],
            source_excerpt_sha256=row["source_excerpt_sha256"],
            source_excerpt_start=row["source_excerpt_start"],
            source_excerpt_end=row["source_excerpt_end"],
            source_status=row["source_status"],
            signals=EditionSignals.model_validate_json(row["signals_json"]),
            created_at=row["created_at"],
            supersedes_edition_id=row["supersedes_edition_id"],
            revision_reason=row["revision_reason"],
            source_snapshots=snapshots,
            claims=claims,
            revision_events=events,
        )

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
