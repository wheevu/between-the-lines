import sqlite3
from pathlib import Path

import pytest

from app.models import (
    AnalysisResult,
    AnalysisStatus,
    ArticleEditionCreate,
    ClaimLedgerEntryCreate,
    Language,
    SegmentResult,
    SourceSnapshotCreate,
)
from app.provenance import text_hash
from app.store import Store


def _edition_request(**overrides: object) -> ArticleEditionCreate:
    values: dict[str, object] = {
        "source_language": Language.ENGLISH,
        "source_text": "A report dated 2024-01-02 names Alice Smith.",
    }
    values.update(overrides)
    return ArticleEditionCreate.model_validate(values)


def _completed_analysis(store: Store) -> str:
    analysis = store.create_analysis()
    store.update_analysis(
        analysis.id,
        status=AnalysisStatus.COMPLETE,
        stage="Ready",
        progress=100,
        result=AnalysisResult(
            source_language=Language.ENGLISH,
            segments=[
                SegmentResult(
                    id="p1s1",
                    paragraph_index=0,
                    sentence_index=0,
                    source_text="A source-bound claim.",
                    translations=[],
                )
            ],
        ),
    )
    return analysis.id


def test_ledger_rejects_forged_and_malformed_hashes(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()

    with pytest.raises(ValueError, match="does not match"):
        store.create_article_edition(
            "article-1",
            _edition_request(source_sha256=text_hash("different source")),
        )
    with pytest.raises(ValueError, match="snapshot hash"):
        store.create_article_edition(
            "article-1",
            _edition_request(
                source_url="https://example.com/story",
                source_snapshots=[
                    SourceSnapshotCreate(
                        url="https://example.com/story",
                        excerpt="A report dated 2024-01-02 names Alice Smith.",
                        source_sha256=text_hash("different source"),
                        end_offset=len("A report dated 2024-01-02 names Alice Smith."),
                    )
                ],
            ),
        )

    with pytest.raises(ValueError):
        _edition_request(source_sha256="not-a-sha256")
    with pytest.raises(ValueError):
        SourceSnapshotCreate(source_sha256="not-a-sha256")


def test_excerpt_only_keeps_an_asserted_full_source_hash_private(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()
    excerpt = "A public, source-bound claim."
    asserted_full_hash = text_hash("Private full source with additional material.")

    edition = store.create_article_edition(
        "article-1",
        _edition_request(
            source_text=None,
            source_sha256=asserted_full_hash,
            source_excerpt=excerpt,
            claims=[ClaimLedgerEntryCreate(text=excerpt, end_offset=len(excerpt))],
        ),
    )

    assert edition.source_sha256 == asserted_full_hash
    assert edition.source_excerpt_sha256 == text_hash(excerpt)
    assert edition.claims[0].evidence_links[0].quote == excerpt

    excerpt_only = store.create_article_edition(
        "article-2",
        _edition_request(source_text=None, source_excerpt=excerpt),
    )
    assert excerpt_only.source_sha256 == text_hash(excerpt)


def test_claim_text_and_offsets_must_match_supplied_material(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()

    with pytest.raises(ValueError, match="claim text does not match"):
        store.create_article_edition(
            "article-1",
            _edition_request(
                source_text="The source says one thing.",
                claims=[ClaimLedgerEntryCreate(text="A fabricated claim", end_offset=18)],
            ),
        )

    with pytest.raises(ValueError, match="must match a stored source snapshot"):
        store.create_article_edition(
            "article-2",
            _edition_request(
                source_text=None,
                source_excerpt="The stored excerpt.",
                claims=[ClaimLedgerEntryCreate(text="An unrelated claim.", end_offset=19)],
            ),
        )


def test_evidence_links_use_only_snapshots_with_an_exact_span_match(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()
    claim = "Bound claim."

    edition = store.create_article_edition(
        "article-1",
        _edition_request(
            source_text=None,
            source_sha256=text_hash("Private complete source."),
            source_snapshots=[
                SourceSnapshotCreate(excerpt="Unrelated.", end_offset=len("Unrelated.")),
                SourceSnapshotCreate(
                    excerpt=claim,
                    start_offset=100,
                    end_offset=100 + len(claim),
                ),
            ],
            claims=[
                ClaimLedgerEntryCreate(
                    text=claim,
                    start_offset=100,
                    end_offset=100 + len(claim),
                )
            ],
        ),
    )

    evidence_links = edition.claims[0].evidence_links
    assert len(evidence_links) == 1
    bound_snapshot = next(
        snapshot for snapshot in edition.source_snapshots if snapshot.excerpt == claim
    )
    assert evidence_links[0].snapshot_id == bound_snapshot.id
    assert evidence_links[0].quote == claim


def test_store_reads_do_not_seed_a_completed_analysis(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()
    article_id = _completed_analysis(store)

    assert store.get_article_ledger(article_id).editions == []
    assert store.export_article(article_id).ledger.editions == []
    assert store.get_article_ledger(article_id).editions == []

    seeded = store.ensure_article_ledger(article_id)
    assert seeded is not None
    assert len(seeded.editions) == 1


def test_same_url_drift_is_changed_but_matching_content_is_duplicate(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()
    url = "https://example.com/story/?utm_source=test"

    first = store.create_article_edition(
        "article-1",
        _edition_request(source_url=url, source_text="The report changed in 2024."),
    )
    changed = store.create_article_edition(
        "article-1",
        _edition_request(
            source_url="https://example.com/story/",
            source_text="The report changed in 2025.",
        ),
    )
    duplicate = store.create_article_edition(
        "article-1",
        _edition_request(source_url=url, source_text="The report changed in 2024."),
    )

    changed_snapshot = changed.source_snapshots[0]
    duplicate_snapshot = duplicate.source_snapshots[0]
    assert changed_snapshot.status == "changed"
    assert changed_snapshot.duplicate_of_id is None
    assert duplicate_snapshot.status == "duplicate"
    assert duplicate_snapshot.duplicate_of_id == first.source_snapshots[0].id


def test_edition_signals_are_bounded_to_the_stored_excerpt(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()
    source_text = "Visible 2024." + (" filler" * 400) + " HiddenPerson 9999."

    edition = store.create_article_edition(
        "article-1",
        _edition_request(source_text=source_text, source_excerpt="Visible 2024."),
    )

    assert edition.signals.numbers == ["2024"]
    assert "hiddenperson" not in edition.signals.terminology
    assert "9999" not in edition.signals.numbers


def test_ledger_rejects_inverted_and_out_of_range_spans(tmp_path: Path) -> None:
    store = Store(tmp_path / "ledger.sqlite3")
    store.initialize()

    with pytest.raises(ValueError, match="source excerpt span"):
        store.create_article_edition(
            "article-1",
            _edition_request(source_text="abcdef", source_excerpt="abc", source_excerpt_start=5),
        )
    with pytest.raises(ValueError, match="does not match"):
        store.create_article_edition(
            "article-1",
            _edition_request(source_text="abcdef", source_excerpt="xyz"),
        )
    with pytest.raises(ValueError, match="claim span"):
        store.create_article_edition(
            "article-1",
            _edition_request(
                source_text="abcdef",
                claims=[ClaimLedgerEntryCreate(text="ab", start_offset=3, end_offset=2)],
            ),
        )
    with pytest.raises(ValueError, match="claim span"):
        store.create_article_edition(
            "article-1",
            _edition_request(
                source_text="abcdef",
                claims=[ClaimLedgerEntryCreate(text="abc", start_offset=4, end_offset=7)],
            ),
        )


def test_ledger_does_not_trust_a_current_version_without_required_tables(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(sqlite3.DatabaseError, match="missing table"):
        Store(path).initialize()


def test_ledger_does_not_trust_a_current_version_without_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE article_editions (id TEXT PRIMARY KEY)")
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(sqlite3.DatabaseError, match="missing columns"):
        Store(path).initialize()
