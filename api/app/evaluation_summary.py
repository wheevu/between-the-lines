import csv
import json
from collections import Counter
from io import StringIO
from pathlib import Path

from app.feedback_export import write_feedback

EXPECTED_DIRECTIONS = {
    "en→vi",
    "en→ko",
    "vi→en",
    "vi→ko",
    "ko→en",
    "ko→vi",
}
REVIEW_SET = Path(__file__).parents[1] / "evaluation" / "review-set.json"


def summarize_database(database_path: Path) -> dict[str, object]:
    output = StringIO()
    write_feedback(database_path, output)
    try:
        review_set = json.loads(REVIEW_SET.read_text())
    except (OSError, ValueError) as error:
        return {
            "ready_for_evidence_layer_decision": False,
            "passage_reviews": 0,
            "passage_reviews_by_direction": {},
            "passage_verdicts_by_direction": {
                direction: {} for direction in sorted(EXPECTED_DIRECTIONS)
            },
            "meaning_risk_judgments": 0,
            "decided_meaning_risk_judgments": 0,
            "meaning_risk_helpful_rate": None,
            "written_omissions": 0,
            "blockers": [f"The reviewer review-set gate could not be read: {error}"],
        }
    return summarize_rows(
        list(csv.DictReader(StringIO(output.getvalue()))),
        passage_analysis_ids=set(review_set["news_passage_analysis_ids"]),
        meaning_analysis_ids=set(review_set["news_passage_analysis_ids"])
        | set(review_set["risk_extension_analysis_ids"]),
    )


def summarize_rows(
    rows: list[dict[str, str]],
    passage_analysis_ids: set[str] | None = None,
    meaning_analysis_ids: set[str] | None = None,
) -> dict[str, object]:
    passage_rows = [
        row
        for row in rows
        if row["scope"] == "passage"
        and (passage_analysis_ids is None or row.get("analysis_id") in passage_analysis_ids)
    ]
    meaning_rows = [
        row
        for row in rows
        if row["scope"] == "flag"
        and row["kind"] == "meaning-risk"
        and (meaning_analysis_ids is None or row.get("analysis_id") in meaning_analysis_ids)
    ]
    decided_meaning = [row for row in meaning_rows if row["verdict"] in {"helpful", "incorrect"}]
    helpful_meaning = sum(row["verdict"] == "helpful" for row in decided_meaning)
    helpful_rate = round(helpful_meaning / len(decided_meaning), 3) if decided_meaning else None

    passage_directions = Counter(
        f"{row['source_language']}→{row['target_language']}" for row in passage_rows
    )
    passage_verdicts = {
        direction: Counter(
            row["verdict"]
            for row in passage_rows
            if f"{row['source_language']}→{row['target_language']}" == direction
        )
        for direction in sorted(EXPECTED_DIRECTIONS)
    }

    blockers = []
    if len(passage_rows) < 12:
        blockers.append("Collect both target-language reviews for six passages.")
    underrepresented = sorted(
        direction for direction in EXPECTED_DIRECTIONS if passage_directions[direction] < 2
    )
    if underrepresented:
        blockers.append(f"Collect at least two reviews for: {', '.join(underrepresented)}.")
    if len(decided_meaning) < 5:
        blockers.append("Collect at least five decided meaning-risk judgments.")
    elif helpful_rate is not None and helpful_rate < 0.8:
        blockers.append("Meaning-risk usefulness is below the 80% continuation gate.")

    weak_directions = sorted(
        direction
        for direction, verdicts in passage_verdicts.items()
        if verdicts["incorrect"] > verdicts["helpful"]
    )
    if weak_directions:
        blockers.append(
            f"More passage reviews were negative than positive for: {', '.join(weak_directions)}."
        )

    return {
        "ready_for_evidence_layer_decision": not blockers,
        "passage_reviews": len(passage_rows),
        "passage_reviews_by_direction": dict(sorted(passage_directions.items())),
        "passage_verdicts_by_direction": {
            direction: dict(verdicts) for direction, verdicts in passage_verdicts.items()
        },
        "meaning_risk_judgments": len(meaning_rows),
        "decided_meaning_risk_judgments": len(decided_meaning),
        "meaning_risk_helpful_rate": helpful_rate,
        "written_omissions": sum(
            bool((row.get("correction") or "").strip()) for row in passage_rows
        ),
        "blockers": blockers,
    }
