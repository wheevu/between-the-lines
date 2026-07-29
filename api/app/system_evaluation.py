import json
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from app.evidence_evaluation import validate_adjudication
from app.evidence_retrieval import canonicalize_url
from app.models import ClaimCheckResult


def summarize_system_run(
    adjudication_path: Path,
    selection_path: Path,
    results_path: Path,
) -> dict[str, object]:
    gold_summary = validate_adjudication(adjudication_path, selection_path)
    blockers = []
    if not gold_summary["ready_for_system_evaluation"]:
        blockers.append("The independent gold adjudication is not ready.")

    adjudication = json.loads(adjudication_path.read_text())
    results = json.loads(results_path.read_text())
    if results.get("schema_version") != 1:
        blockers.append("Use system-run schema version 1.")
    if results.get("complete") is not True:
        blockers.append("Finish the entire frozen system run before scoring it.")
    if results.get("adjudication_sha256") != sha256(adjudication_path.read_bytes()).hexdigest():
        blockers.append("The system run does not match the frozen adjudication.")

    gold_by_id = {item["candidate_id"]: item for item in adjudication.get("claims", [])}
    parsed: dict[str, ClaimCheckResult] = {}
    invalid_results = []
    duplicate_ids = []
    for raw in results.get("claims", []):
        try:
            result = ClaimCheckResult.model_validate(raw)
        except ValidationError as error:
            invalid_results.append(str(error))
            continue
        candidate_id = result.claim.id
        if candidate_id in parsed:
            duplicate_ids.append(candidate_id)
        parsed[candidate_id] = result

    if invalid_results:
        blockers.append("Fix invalid claim-result records.")
    if duplicate_ids:
        blockers.append("Remove duplicate system claim results.")
    if set(parsed) != set(gold_by_id):
        blockers.append("Run the exact 30 adjudicated claims.")

    rows = []
    duplicate_rule_violations = []
    invalid_urls = []
    invalid_assessment_references: list[dict[str, object]] = []
    for candidate_id in sorted(set(parsed) & set(gold_by_id)):
        result = parsed[candidate_id]
        gold_claim = gold_by_id[candidate_id]
        if (
            result.claim.source_quote != gold_claim["source_quote"]
            or result.claim.standalone_claim != gold_claim["standalone_claim"]
        ):
            blockers.append(f"System claim text changed for {candidate_id}.")
            continue
        reference_issues = _assessment_reference_issues(result)
        if reference_issues:
            invalid_assessment_references.append(
                {
                    "candidate_id": candidate_id,
                    "issues": reference_issues,
                }
            )
        expected_status = gold_claim["gold"]["expected_status"]
        actual_status = result.assessment.status.value
        top_five_urls = []
        for evidence in result.evidence[:5]:
            try:
                top_five_urls.append(canonicalize_url(evidence.url))
            except ValueError:
                invalid_urls.append(evidence.url)
        retrieval_hit = (
            bool(set(top_five_urls) & _gold_urls(gold_claim["gold"]))
            if expected_status != "insufficient"
            else None
        )
        if not _status_obeys_independence(result):
            duplicate_rule_violations.append(candidate_id)
        rows.append(
            {
                "candidate_id": candidate_id,
                "source_language": gold_claim["source_language"],
                "expected_status": expected_status,
                "actual_status": actual_status,
                "status_correct": actual_status == expected_status,
                "retrieval_hit_at_5": retrieval_hit,
                "top_five_evidence": min(5, len(result.evidence)),
                "retrieval_failures": len(result.retrieval_failures),
            }
        )

    if invalid_urls:
        blockers.append("System evidence contains invalid URLs.")
    if invalid_assessment_references:
        blockers.append("Fix invalid assessment-to-evidence references.")
    resolved_rows = [row for row in rows if row["expected_status"] != "insufficient"]
    abstention_rows = [row for row in rows if row["expected_status"] == "insufficient"]
    retrieval_rows = [row for row in rows if row["retrieval_hit_at_5"] is not None]
    by_language = {
        language: {
            "claims": len(language_rows),
            "status_accuracy": _rate(row["status_correct"] for row in language_rows),
            "retrieval_hit_at_5": _rate(
                row["retrieval_hit_at_5"]
                for row in language_rows
                if row["retrieval_hit_at_5"] is not None
            ),
        }
        for language in ("en", "vi", "ko")
        if (language_rows := [row for row in rows if row["source_language"] == language])
    }
    language_rates = [item["status_accuracy"] for item in by_language.values()]
    language_gap = max(language_rates) - min(language_rates) if language_rates else None
    retrieval_rate = _rate(row["retrieval_hit_at_5"] for row in retrieval_rows)
    resolved_rate = _rate(row["status_correct"] for row in resolved_rows)
    abstention_rate = _rate(row["status_correct"] for row in abstention_rows)
    complete = not blockers and len(rows) == 30
    automatic_gates_passed = (
        complete
        and retrieval_rate is not None
        and retrieval_rate >= 0.8
        and resolved_rate is not None
        and resolved_rate >= 0.8
        and abstention_rate is not None
        and abstention_rate >= 0.85
        and language_gap is not None
        and language_gap <= 0.1
        and not duplicate_rule_violations
    )
    return {
        "claims": len(rows),
        "status_accuracy": _rate(row["status_correct"] for row in rows),
        "resolved_status_accuracy": resolved_rate,
        "abstention_accuracy": abstention_rate,
        "retrieval_hit_at_5": retrieval_rate,
        "status_accuracy_by_language": by_language,
        "largest_language_gap": language_gap,
        "duplicate_rule_violations": duplicate_rule_violations,
        "invalid_assessment_references": invalid_assessment_references,
        "claims_with_partial_retrieval": sum(row["retrieval_failures"] > 0 for row in rows),
        "citation_judgments": 0,
        "automatic_gates_passed": automatic_gates_passed,
        "ready_for_human_citation_review": complete,
        "rows": rows,
        "blockers": list(dict.fromkeys(blockers)),
        "note": (
            "URL matches measure frozen acceptable-evidence retrieval only. "
            "Human review must judge whether each cited excerpt supports its stated stance."
        ),
    }


def _gold_urls(gold: dict[str, object]) -> set[str]:
    return {
        canonicalize_url(item["url"])
        for evidence_set in gold.get("acceptable_evidence_sets", [])
        for item in evidence_set.get("items", [])
    }


def _status_obeys_independence(result: ClaimCheckResult) -> bool:
    status = result.assessment.status.value
    groups = []
    if status in {"supported", "mixed"}:
        groups.append(result.assessment.support_evidence_ids)
    if status in {"disputed", "mixed"}:
        groups.append(result.assessment.challenge_evidence_ids)
    evidence_by_id = {item.id: item for item in result.evidence}
    for ids in groups:
        items = [evidence_by_id[item_id] for item_id in ids if item_id in evidence_by_id]
        publishers = {item.publisher_key or item.publisher.strip().casefold() for item in items}
        if len(publishers) < 2 or len({item.cluster_id for item in items}) < 2:
            return False
    return True


def _assessment_reference_issues(result: ClaimCheckResult) -> list[str]:
    issues = []
    if result.assessment.claim_id != result.claim.id:
        issues.append("Assessment claim_id does not match the frozen claim.")

    evidence_ids = [item.id for item in result.evidence]
    duplicate_evidence_ids = sorted(
        item_id for item_id in set(evidence_ids) if evidence_ids.count(item_id) > 1
    )
    if duplicate_evidence_ids:
        issues.append("Evidence IDs must be unique within a claim result.")

    groups = {
        "supports": result.assessment.support_evidence_ids,
        "disputes": result.assessment.challenge_evidence_ids,
        "context": result.assessment.context_evidence_ids,
    }
    cited_ids = [item_id for ids in groups.values() for item_id in ids]
    if len(cited_ids) != len(set(cited_ids)):
        issues.append("An evidence ID cannot appear in more than one assessment role.")
    if set(cited_ids) - set(evidence_ids):
        issues.append("Every cited evidence ID must exist in the result evidence.")
    evidence_by_id = {item.id: item for item in result.evidence}
    if any(
        item_id in evidence_by_id
        and (
            evidence_by_id[item_id].stance is None
            or evidence_by_id[item_id].stance.value != expected_stance
        )
        for expected_stance, ids in groups.items()
        for item_id in ids
    ):
        issues.append("Every cited evidence stance must match its assessment role.")
    return issues


def _rate(values) -> float | None:
    collected = list(values)
    return round(sum(bool(value) for value in collected) / len(collected), 3) if collected else None
