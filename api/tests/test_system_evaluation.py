import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path

from app.citation_evaluation import (
    FIELDS,
    summarize_citation_review,
    write_citation_review_sheet,
)
from app.system_evaluation import summarize_system_run


def test_complete_matching_run_reports_frozen_metrics(tmp_path: Path) -> None:
    selection, adjudication, results = _write_frozen_run(tmp_path)

    summary = summarize_system_run(adjudication, selection, results)

    assert summary["claims"] == 30
    assert summary["status_accuracy"] == 1.0
    assert summary["retrieval_hit_at_5"] == 1.0
    assert summary["largest_language_gap"] == 0
    assert summary["duplicate_rule_violations"] == []
    assert summary["invalid_assessment_references"] == []
    assert not summary["automatic_gates_passed"]
    assert summary["ready_for_human_citation_review"]
    assert summary["citation_judgments"] == 0
    assert summary["abstention_accuracy"] is None


def test_citation_review_hash_binds_every_independent_judgment(tmp_path: Path) -> None:
    selection, adjudication, results = _write_frozen_run(tmp_path)
    prepared = StringIO()
    write_citation_review_sheet(adjudication, selection, results, prepared)
    prepared.seek(0)
    rows = list(csv.DictReader(prepared))
    assert len(rows) == 60

    review = tmp_path / "citation-review.csv"
    with review.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "relevant_to_claim": "yes",
                    "excerpt_matches_source": "yes",
                    "stance_correct": "yes",
                    "reviewer_id": "reviewer-c",
                    "reviewer_role": "independent",
                }
            )

    summary = summarize_citation_review(adjudication, selection, results, review)

    assert summary["expected_citations"] == 60
    assert summary["reviewed_citations"] == 60
    assert summary["citation_correctness"] == 1.0
    assert summary["largest_language_gap"] == 0
    assert summary["ready_for_reporting"]
    assert summary["citation_gate_passed"]
    assert summary["blockers"] == []


def test_unsure_or_author_only_citation_review_never_passes(tmp_path: Path) -> None:
    selection, adjudication, results = _write_frozen_run(tmp_path)
    prepared = StringIO()
    write_citation_review_sheet(adjudication, selection, results, prepared)
    prepared.seek(0)
    rows = list(csv.DictReader(prepared))
    review = tmp_path / "citation-review.csv"
    with review.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        for index, row in enumerate(rows):
            writer.writerow(
                {
                    **row,
                    "relevant_to_claim": "unsure" if index == 0 else "yes",
                    "excerpt_matches_source": "yes",
                    "stance_correct": "yes",
                    "reviewer_id": "project-author",
                    "reviewer_role": "author",
                }
            )

    summary = summarize_citation_review(adjudication, selection, results, review)

    assert summary["ready_for_reporting"]
    assert summary["undecided_citations"] == 1
    assert summary["independent_citations"] == 0
    assert summary["citation_correctness"] == 0.983
    assert not summary["citation_gate_passed"]


def test_altered_citation_and_unknown_assessment_reference_fail_closed(
    tmp_path: Path,
) -> None:
    selection, adjudication, results = _write_frozen_run(tmp_path)
    result_data = json.loads(results.read_text())
    result_data["claims"][0]["assessment"]["support_evidence_ids"].append("missing-id")
    results.write_text(json.dumps(result_data))

    system_summary = summarize_system_run(adjudication, selection, results)

    assert not system_summary["ready_for_human_citation_review"]
    assert system_summary["invalid_assessment_references"] == [
        {
            "candidate_id": "claim-0",
            "issues": ["Every cited evidence ID must exist in the result evidence."],
        }
    ]


def test_cited_stance_must_match_assessment_role(tmp_path: Path) -> None:
    selection, adjudication, results = _write_frozen_run(tmp_path)
    result_data = json.loads(results.read_text())
    result_data["claims"][0]["evidence"][0]["stance"] = "disputes"
    results.write_text(json.dumps(result_data))

    system_summary = summarize_system_run(adjudication, selection, results)

    assert not system_summary["ready_for_human_citation_review"]
    assert system_summary["invalid_assessment_references"] == [
        {
            "candidate_id": "claim-0",
            "issues": ["Every cited evidence stance must match its assessment role."],
        }
    ]


def test_altered_immutable_citation_data_is_rejected(tmp_path: Path) -> None:
    selection, adjudication, results = _write_frozen_run(tmp_path)
    prepared = StringIO()
    write_citation_review_sheet(adjudication, selection, results, prepared)
    prepared.seek(0)
    rows = list(csv.DictReader(prepared))
    rows[0]["excerpt"] = "A reviewer must not rewrite the system excerpt."
    review = tmp_path / "citation-review.csv"
    with review.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "relevant_to_claim": "yes",
                    "excerpt_matches_source": "yes",
                    "stance_correct": "yes",
                    "reviewer_id": "reviewer-c",
                    "reviewer_role": "independent",
                }
            )

    summary = summarize_citation_review(adjudication, selection, results, review)

    assert not summary["ready_for_reporting"]
    assert not summary["citation_gate_passed"]
    assert summary["altered_rows"] == [
        {
            "candidate_id": "claim-0",
            "evidence_id": "evidence-0-one",
            "fields": ["excerpt"],
        }
    ]


def _write_frozen_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    results = tmp_path / "results.json"
    with selection.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["candidate_id", "include_in_30"])
        writer.writeheader()
        for index in range(30):
            writer.writerow({"candidate_id": f"claim-{index}", "include_in_30": "yes"})

    gold_claims = [_gold_claim(index) for index in range(30)]
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": gold_claims,
            }
        )
    )
    results.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "complete": True,
                "adjudication_sha256": sha256(adjudication.read_bytes()).hexdigest(),
                "generated_at": datetime.now(UTC).isoformat(),
                "claims": [_system_result(index) for index in range(30)],
            }
        )
    )
    return selection, adjudication, results


def _gold_claim(index: int) -> dict[str, object]:
    language = ("en", "vi", "ko")[index // 10]
    items = [
        {
            "url": f"https://{host}/report",
            "publisher": publisher,
            "language": language,
            "stance": "supports",
            "excerpt": excerpt,
            "published_at": "2026-07-01",
        }
        for host, publisher, excerpt in (
            ("one.example", "Publisher One", "First exact evidence excerpt."),
            ("two.example", "Publisher Two", "Second exact evidence excerpt."),
        )
    ]
    return {
        "candidate_id": f"claim-{index}",
        "source_language": language,
        "source_quote": f"Quote {index}",
        "standalone_claim": f"Claim {index}",
        "gold": {
            "expected_status": "supported",
            "acceptable_evidence_sets": [
                {
                    "items": items,
                    "independence_note": "The publishers report independently.",
                }
            ],
            "checked_at": datetime.now(UTC).isoformat(),
            "rationale": "Two independent sources support the claim.",
            "search_notes": "",
            "adjudicators": [
                {"id": "reviewer-a", "role": "independent"},
                {"id": "reviewer-b", "role": "independent"},
            ],
            "adjudication_notes": "",
        },
    }


def _system_result(index: int) -> dict[str, object]:
    evidence = [
        {
            "id": f"evidence-{index}-{suffix}",
            "url": f"https://{host}/report",
            "publisher": publisher,
            "publisher_key": host,
            "language": "en",
            "excerpt": excerpt,
            "source_type": "direct-reporting",
            "content_hash": f"hash-{suffix}",
            "cluster_id": f"cluster-{index}-{suffix}",
            "relevance": relevance,
            "stance": "supports",
        }
        for suffix, host, publisher, excerpt, relevance in (
            ("one", "one.example", "Publisher One", "First exact evidence excerpt.", 0.9),
            ("two", "two.example", "Publisher Two", "Second exact evidence excerpt.", 0.8),
        )
    ]
    return {
        "claim": {
            "id": f"claim-{index}",
            "source_quote": f"Quote {index}",
            "segment_ids": ["p1s1"],
            "standalone_claim": f"Claim {index}",
            "claim_type": "fact",
            "entities": [],
            "dates": [],
            "numbers": [],
            "reason": "Frozen evaluation claim.",
        },
        "queries": [],
        "evidence": evidence,
        "assessment": {
            "claim_id": f"claim-{index}",
            "status": "supported",
            "explanation": "Two independent sources support the claim.",
            "support_evidence_ids": [item["id"] for item in evidence],
            "challenge_evidence_ids": [],
            "context_evidence_ids": [],
            "limitations": [],
        },
        "retrieval_failures": [],
    }
