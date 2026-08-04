import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.evidence_evaluation import (
    _claim_issues,
    _empty_gold,
    merge_adjudication,
    split_adjudication,
    validate_adjudication,
)


def write_selection(path: Path) -> None:
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["candidate_id", "include_in_30"])
        writer.writeheader()
        for index in range(30):
            writer.writerow(
                {
                    "candidate_id": f"claim-{index}",
                    "include_in_30": "yes",
                }
            )


def claim(index: int, *, complete: bool) -> dict[str, object]:
    language = ("en", "vi", "ko")[index // 10]
    gold = {
        "expected_status": "supported" if complete else None,
        "acceptable_evidence_sets": (
            [
                {
                    "items": [
                        {
                            "url": "https://one.example/report",
                            "publisher": "Publisher One",
                            "language": language,
                            "stance": "supports",
                            "excerpt": "First exact evidence excerpt.",
                            "published_at": "2026-07-01",
                        },
                        {
                            "url": "https://two.example/report",
                            "publisher": "Publisher Two",
                            "language": language,
                            "stance": "supports",
                            "excerpt": "Second exact evidence excerpt.",
                            "published_at": "2026-07-02",
                        },
                    ],
                    "independence_note": "The publishers report independently.",
                }
            ]
            if complete
            else []
        ),
        "checked_at": datetime.now(UTC).isoformat() if complete else None,
        "rationale": "Two independent sources support the claim." if complete else "",
        "search_notes": "",
        "adjudicators": (
            [
                {"id": "reviewer-a", "role": "independent"},
                {"id": "reviewer-b", "role": "independent"},
            ]
            if complete
            else []
        ),
        "adjudication_notes": "",
    }
    return {
        "candidate_id": f"claim-{index}",
        "source_language": language,
        "gold": gold,
    }


def test_incomplete_gold_labels_cannot_be_used_for_system_evaluation(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    write_selection(selection)
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": [claim(index, complete=False) for index in range(30)],
            }
        )
    )

    summary = validate_adjudication(adjudication, selection)

    assert summary["ready_claims"] == 0
    assert not summary["ready_for_system_evaluation"]
    assert len(summary["claim_issues"]) == 30


def test_complete_balanced_gold_labels_pass_structural_validation(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    write_selection(selection)
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )

    summary = validate_adjudication(adjudication, selection)

    assert summary["ready_claims"] == 30
    assert summary["ready_for_system_evaluation"]


def write_template(tmp_path: Path) -> Path:
    selection = tmp_path / "selection.csv"
    write_selection(selection)
    template = tmp_path / "template.json"
    template.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "purpose": "Frozen gold template.",
                "claims": [claim(index, complete=False) for index in range(30)],
            }
        )
    )
    return template


def test_split_creates_two_empty_reviewer_workbooks(tmp_path: Path) -> None:
    template = write_template(tmp_path)

    result = split_adjudication(template, tmp_path / "packets")

    assert set(result["packets"]) == {"reviewer-a", "reviewer-b"}
    for packet_path in result["packets"].values():
        packet = json.loads(Path(packet_path).read_text())
        assert packet["reviewer"]["role"] == "independent"
        assert len(packet["claims"]) == 30
        expected = json.loads(template.read_text())["claims"]
        assert all(packet["claims"][i] == expected[i] for i in range(30))
        assert all(_empty_gold(entry) for entry in packet["claims"])


def test_split_refuses_a_template_that_already_contains_review_work(tmp_path: Path) -> None:
    template = write_template(tmp_path)
    data = json.loads(template.read_text())
    data["claims"][0]["gold"]["rationale"] = "Already reviewed."
    template.write_text(json.dumps(data))

    try:
        split_adjudication(template, tmp_path / "packets")
    except ValueError as error:
        assert "already contains review work" in str(error)
    else:
        raise AssertionError("splitting reviewed work should fail")


def test_merge_combines_complete_agreeing_packets(tmp_path: Path) -> None:
    template = write_template(tmp_path)
    template_data = json.loads(template.read_text())
    packet_a = tmp_path / "reviewer-a.json"
    packet_b = tmp_path / "reviewer-b.json"
    packet_a.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-a", "role": "independent"},
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )
    packet_b.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-b", "role": "independent"},
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )
    output = tmp_path / "gold.json"
    selection = tmp_path / "selection.csv"

    result = merge_adjudication(packet_a, packet_b, template, output, selection)

    assert result["disagreements"] == []
    assert result["summary"]["ready_for_system_evaluation"]
    merged = json.loads(output.read_text())
    assert merged["selection_sha256"] == template_data["selection_sha256"]
    assert all(
        merged["claims"][i]["candidate_id"] == template_data["claims"][i]["candidate_id"]
        for i in range(30)
    )
    assert merged["claims"][0]["gold"]["adjudicators"] == [
        {"id": "reviewer-a", "role": "independent"},
        {"id": "reviewer-b", "role": "independent"},
    ]


def test_merge_preserves_a_status_disagreement(tmp_path: Path) -> None:
    template = write_template(tmp_path)
    template_data = json.loads(template.read_text())
    packet_a = tmp_path / "reviewer-a.json"
    packet_b = tmp_path / "reviewer-b.json"
    packet_a.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-a", "role": "independent"},
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )
    disputed_first = claim(0, complete=True)
    disputed_first["gold"]["expected_status"] = "disputed"
    disputed_first["gold"]["acceptable_evidence_sets"] = [
        {
            "items": [
                {
                    "url": "https://one.example/report",
                    "publisher": "Publisher One",
                    "language": "en",
                    "stance": "disputes",
                    "excerpt": "First disputing excerpt.",
                    "published_at": "2026-07-01",
                },
                {
                    "url": "https://two.example/report",
                    "publisher": "Publisher Two",
                    "language": "en",
                    "stance": "disputes",
                    "excerpt": "Second disputing excerpt.",
                    "published_at": "2026-07-02",
                },
            ],
            "independence_note": "The publishers report independently.",
        }
    ]
    disputed_first["gold"]["rationale"] = "The same outlet later corrected the figure."
    packet_b.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-b", "role": "independent"},
                "claims": [
                    disputed_first
                ] + [claim(index, complete=True) for index in range(1, 30)],
            }
        )
    )
    output = tmp_path / "gold.json"
    selection = tmp_path / "selection.csv"

    result = merge_adjudication(packet_a, packet_b, template, output, selection)

    assert result["disagreements"] == ["claim-0"]
    assert not result["summary"]["ready_for_system_evaluation"]
    merged = json.loads(output.read_text())
    assert merged["claims"][0]["gold"]["expected_status"] is None
    assert "Reviewers disagree" in merged["claims"][0]["gold"]["adjudication_notes"]


def test_merge_rejects_tampered_hash_bound_fields(tmp_path: Path) -> None:
    template = write_template(tmp_path)
    template_data = json.loads(template.read_text())
    packet_a = tmp_path / "reviewer-a.json"
    packet_b = tmp_path / "reviewer-b.json"
    packet_a.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-a", "role": "independent"},
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )
    altered = json.loads(packet_a.read_text())
    altered["reviewer"] = {"id": "reviewer-b", "role": "independent"}
    altered["claims"][3]["source_language"] = "ko"
    packet_b.write_text(json.dumps(altered))

    try:
        merge_adjudication(
            packet_a,
            packet_b,
            template,
            tmp_path / "gold.json",
            tmp_path / "selection.csv",
        )
    except ValueError as error:
        assert "changed source_language" in str(error)
    else:
        raise AssertionError("tampered packets should fail to merge")


def test_merge_rejects_an_incomplete_packet(tmp_path: Path) -> None:
    template = write_template(tmp_path)
    template_data = json.loads(template.read_text())
    packet_a = tmp_path / "reviewer-a.json"
    packet_b = tmp_path / "reviewer-b.json"
    packet_a.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-a", "role": "independent"},
                "claims": [claim(index, complete=True) for index in range(30)],
            }
        )
    )
    packet_b.write_text(
        json.dumps(
            {
                **template_data,
                "reviewer": {"id": "reviewer-b", "role": "independent"},
                "claims": [claim(index, complete=False) for index in range(30)],
            }
        )
    )

    try:
        merge_adjudication(
            packet_a,
            packet_b,
            template,
            tmp_path / "gold.json",
            tmp_path / "selection.csv",
        )
    except ValueError as error:
        assert "reviewer-b left claim claim-0 incomplete" in str(error)
    else:
        raise AssertionError("incomplete packets should fail to merge")


def test_wrong_claim_set_and_unexplained_insufficient_status_are_blocked(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.csv"
    adjudication = tmp_path / "gold.json"
    write_selection(selection)
    claims = [claim(index, complete=True) for index in range(30)]
    claims[0]["candidate_id"] = "not-selected"
    claims[1]["gold"] = {
        "expected_status": "insufficient",
        "acceptable_evidence_sets": [],
        "checked_at": datetime.now(UTC).isoformat(),
        "rationale": "No sufficient evidence was located.",
        "search_notes": "",
        "adjudicators": [
            {"id": "reviewer-a", "role": "independent"},
            {"id": "reviewer-b", "role": "independent"},
        ],
        "adjudication_notes": "",
    }
    adjudication.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "selection_sha256": sha256(selection.read_bytes()).hexdigest(),
                "claims": claims,
            }
        )
    )

    summary = validate_adjudication(adjudication, selection)

    assert not summary["ready_for_system_evaluation"]
    assert "Adjudicate the exact candidate IDs in the frozen selection." in summary["blockers"]
    assert summary["claim_issues"] == [
        {
            "candidate_id": "claim-1",
            "issues": ["An insufficient status needs notes describing the search scope."],
        }
    ]


def test_author_and_duplicate_labels_cannot_satisfy_independent_gold() -> None:
    gold = claim(0, complete=True)["gold"]
    gold["adjudicators"] = [
        {"id": "author", "role": "author"},
        {"id": "reviewer-a", "role": "independent"},
        {"id": "reviewer-a", "role": "independent"},
    ]

    assert "Record at least two distinct independent adjudicators." in _claim_issues({"gold": gold})
