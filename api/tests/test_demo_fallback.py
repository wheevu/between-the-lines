from pathlib import Path

from app.demo_fallback import verify_demo_fallback
from app.models import AnalysisResult, AnalysisStatus
from app.store import Store


def complete_result() -> AnalysisResult:
    return AnalysisResult.model_validate(
        {
            "source_language": "en",
            "segments": [
                {
                    "id": "p1s1",
                    "paragraph_index": 0,
                    "sentence_index": 0,
                    "source_text": "The agency reported 20 cases.",
                    "translations": [
                        {"language": "vi", "text": "Cơ quan báo cáo 20 ca."},
                        {"language": "ko", "text": "당국은 20건을 보고했다."},
                    ],
                }
            ],
        }
    )


def write_guide(path: Path, analysis_id: str) -> None:
    path.write_text(f"[Review](http://127.0.0.1:5173/?analysis={analysis_id})\n")


def test_complete_linked_analysis_is_ready_without_mutating_database(tmp_path: Path) -> None:
    database = tmp_path / "fallback.sqlite3"
    guide = tmp_path / "reviewer-guide.md"
    store = Store(database)
    store.initialize()
    job = store.create_analysis()
    store.update_analysis(
        job.id,
        status=AnalysisStatus.COMPLETE,
        stage="Complete",
        progress=100,
        result=complete_result(),
    )
    write_guide(guide, job.id)
    modified_before = database.stat().st_mtime_ns

    summary = verify_demo_fallback(database, guide)

    assert summary["integrity"] == "ok"
    assert summary["expected_analyses"] == 1
    assert summary["ready_analyses"] == 1
    assert summary["blockers"] == []
    assert summary["ready_for_translation_recording"]
    assert database.stat().st_mtime_ns == modified_before


def test_incomplete_or_missing_linked_analyses_block_recording(tmp_path: Path) -> None:
    database = tmp_path / "fallback.sqlite3"
    guide = tmp_path / "reviewer-guide.md"
    store = Store(database)
    store.initialize()
    incomplete = store.create_analysis()
    missing_id = "00000000-0000-0000-0000-000000000000"
    guide.write_text(
        "\n".join(
            [
                f"[Incomplete](http://localhost:5173/?analysis={incomplete.id})",
                f"[Missing](http://localhost:5173/?analysis={missing_id})",
            ]
        )
    )

    summary = verify_demo_fallback(database, guide)

    assert not summary["ready_for_translation_recording"]
    assert summary["ready_analyses"] == 0
    assert summary["blockers"] == [
        f"Reviewer-guide analysis is not complete: {incomplete.id}",
        f"Missing reviewer-guide analysis: {missing_id}",
    ]


def test_missing_database_is_reported_without_creating_it(tmp_path: Path) -> None:
    database = tmp_path / "missing.sqlite3"
    guide = tmp_path / "reviewer-guide.md"
    write_guide(guide, "00000000-0000-0000-0000-000000000000")

    summary = verify_demo_fallback(database, guide)

    assert not summary["ready_for_translation_recording"]
    assert not database.exists()
    assert summary["blockers"][0] == f"Fallback database does not exist: {database}"


def test_missing_reviewer_guide_is_reported_without_a_traceback(tmp_path: Path) -> None:
    database = tmp_path / "fallback.sqlite3"
    Store(database).initialize()

    summary = verify_demo_fallback(database, tmp_path / "missing.md")

    assert not summary["ready_for_translation_recording"]
    assert summary["expected_analyses"] == 0
    assert summary["blockers"][0].startswith("Could not read reviewer guide:")
