from app.evaluation_summary import EXPECTED_DIRECTIONS, summarize_rows


def test_complete_balanced_review_set_reaches_the_decision_gate() -> None:
    rows = [
        {
            "scope": "passage",
            "source_language": direction[:2],
            "target_language": direction[-2:],
            "kind": "",
            "verdict": "helpful",
            "correction": "",
        }
        for direction in EXPECTED_DIRECTIONS
        for _ in range(2)
    ]
    rows.extend(
        {
            "scope": "flag",
            "source_language": "en",
            "target_language": "vi",
            "kind": "meaning-risk",
            "verdict": verdict,
            "correction": "",
        }
        for verdict in ["helpful", "helpful", "helpful", "helpful", "incorrect"]
    )

    summary = summarize_rows(rows)

    assert summary["ready_for_evidence_layer_decision"] is True
    assert summary["meaning_risk_helpful_rate"] == 0.8


def test_sparse_review_set_reports_coverage_and_judgment_gaps() -> None:
    summary = summarize_rows(
        [
            {
                "scope": "passage",
                "source_language": "en",
                "target_language": "vi",
                "kind": "",
                "verdict": "incorrect",
                "correction": "The modal changed.",
            }
        ]
    )

    assert summary["ready_for_evidence_layer_decision"] is False
    assert summary["written_omissions"] == 1
    assert any("six passages" in blocker for blocker in summary["blockers"])


def test_synthetic_passage_reviews_do_not_fill_the_news_coverage_gate() -> None:
    summary = summarize_rows(
        [
            {
                "analysis_id": "synthetic",
                "scope": "passage",
                "source_language": "ko",
                "target_language": "en",
                "kind": "",
                "verdict": "helpful",
                "correction": "",
            },
            {
                "analysis_id": "synthetic",
                "scope": "flag",
                "source_language": "ko",
                "target_language": "en",
                "kind": "meaning-risk",
                "verdict": "helpful",
                "correction": "",
            },
        ],
        passage_analysis_ids={"news"},
    )

    assert summary["passage_reviews"] == 0
    assert summary["meaning_risk_judgments"] == 1


def test_historical_flags_do_not_contaminate_frozen_meaning_risk_set() -> None:
    rows = [
        {
            "analysis_id": "current",
            "scope": "flag",
            "source_language": "vi",
            "target_language": "en",
            "kind": "meaning-risk",
            "verdict": "helpful",
            "correction": "",
        },
        {
            "analysis_id": "historical",
            "scope": "flag",
            "source_language": "vi",
            "target_language": "en",
            "kind": "meaning-risk",
            "verdict": "incorrect",
            "correction": "",
        },
    ]

    summary = summarize_rows(rows, meaning_analysis_ids={"current"})

    assert summary["meaning_risk_judgments"] == 1
    assert summary["meaning_risk_helpful_rate"] == 1.0
