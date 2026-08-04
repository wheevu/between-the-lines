import csv
import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from app.fact_check_evaluation import summarize_pool_selection

STATUSES = {"supported", "disputed", "mixed", "insufficient"}
STANCES = {"supports", "disputes", "context"}
LANGUAGES = {"en", "vi", "ko"}


def prepare_adjudication(
    pool_path: Path,
    selection_path: Path,
) -> dict[str, object]:
    summary = summarize_pool_selection(pool_path, selection_path)
    if not summary["ready_for_evidence_adjudication"]:
        raise ValueError("The balanced 30-claim selection is not ready.")
    with selection_path.open(newline="") as source:
        selected = [
            row for row in csv.DictReader(source) if row["include_in_30"].strip().lower() == "yes"
        ]
    return {
        "schema_version": 2,
        "selection_sha256": sha256(selection_path.read_bytes()).hexdigest(),
        "purpose": (
            "Human gold evidence and status labels for the frozen 30-claim set. "
            "Do not derive these fields from Between the Lines output."
        ),
        "claims": [
            {
                "candidate_id": row["candidate_id"],
                "case_id": row["case_id"],
                "source_language": row["source_language"],
                "primary_category": row["primary_category"],
                "claim_type": row["claim_type"],
                "source_quote": row["source_quote"],
                "standalone_claim": row["standalone_claim"],
                "gold": {
                    "expected_status": None,
                    "acceptable_evidence_sets": [],
                    "checked_at": None,
                    "rationale": "",
                    "search_notes": "",
                    "adjudicators": [],
                    "adjudication_notes": "",
                },
            }
            for row in selected
        ],
    }


def validate_adjudication(
    adjudication_path: Path,
    selection_path: Path,
) -> dict[str, object]:
    data = json.loads(adjudication_path.read_text())
    claims = data.get("claims", [])
    blockers = []
    if data.get("schema_version") != 2:
        blockers.append("Use adjudication schema version 2.")
    expected_selection_hash = sha256(selection_path.read_bytes()).hexdigest()
    if data.get("selection_sha256") != expected_selection_hash:
        blockers.append("The adjudication does not match the frozen selection sheet.")
    if len(claims) != 30:
        blockers.append("Adjudicate exactly 30 selected claims.")
    candidate_ids = [claim.get("candidate_id") for claim in claims]
    if len(candidate_ids) != len(set(candidate_ids)):
        blockers.append("Remove duplicate adjudicated claims.")
    with selection_path.open(newline="") as source:
        selected_ids = {
            row["candidate_id"]
            for row in csv.DictReader(source)
            if row["include_in_30"].strip().lower() == "yes"
        }
    if set(candidate_ids) != selected_ids:
        blockers.append("Adjudicate the exact candidate IDs in the frozen selection.")
    language_counts = Counter(claim.get("source_language") for claim in claims)
    if language_counts != Counter({"en": 10, "vi": 10, "ko": 10}):
        blockers.append("Adjudicate exactly 10 claims per source language.")

    ready_claims = 0
    claim_issues: list[dict[str, object]] = []
    for claim in claims:
        issues = _claim_issues(claim)
        if issues:
            claim_issues.append(
                {
                    "candidate_id": claim.get("candidate_id"),
                    "issues": issues,
                }
            )
        else:
            ready_claims += 1
    if claim_issues:
        blockers.append("Complete every gold status, evidence set, and adjudication field.")
    return {
        "claims": len(claims),
        "ready_claims": ready_claims,
        "language_counts": dict(sorted(language_counts.items())),
        "claim_issues": claim_issues,
        "ready_for_system_evaluation": not blockers,
        "blockers": blockers,
    }


def _claim_issues(claim: dict[str, object]) -> list[str]:
    issues = []
    gold = claim.get("gold")
    if not isinstance(gold, dict):
        return ["Missing gold object."]
    status = gold.get("expected_status")
    if status not in STATUSES:
        issues.append("Choose a valid expected status.")
    checked_at = gold.get("checked_at")
    if not isinstance(checked_at, str) or not _has_timezone(checked_at):
        issues.append("Record a timezone-aware checked_at timestamp.")
    rationale = gold.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        issues.append("Explain the gold status.")
    search_notes = gold.get("search_notes")
    if status == "insufficient" and (not isinstance(search_notes, str) or not search_notes.strip()):
        issues.append("An insufficient status needs notes describing the search scope.")
    adjudicators = gold.get("adjudicators")
    independent_adjudicators = (
        {
            item["id"].strip()
            for item in adjudicators
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"].strip()
            and item.get("role") == "independent"
        }
        if isinstance(adjudicators, list)
        else set()
    )
    if len(independent_adjudicators) < 2:
        issues.append("Record at least two distinct independent adjudicators.")

    evidence_sets = gold.get("acceptable_evidence_sets")
    if not isinstance(evidence_sets, list):
        issues.append("acceptable_evidence_sets must be a list.")
        return issues
    if status != "insufficient" and not evidence_sets:
        issues.append("A resolved status needs at least one acceptable evidence set.")
    for index, evidence_set in enumerate(evidence_sets, start=1):
        issues.extend(_evidence_set_issues(evidence_set, status, index))
    return issues


def _evidence_set_issues(
    evidence_set: object,
    status: object,
    index: int,
) -> list[str]:
    prefix = f"Evidence set {index}"
    if not isinstance(evidence_set, dict):
        return [f"{prefix} must be an object."]
    items = evidence_set.get("items")
    if not isinstance(items, list) or not items:
        return [f"{prefix} needs evidence items."]
    issues = []
    stance_publishers: dict[str, set[str]] = {
        "supports": set(),
        "disputes": set(),
    }
    stance_hosts: dict[str, set[str]] = {
        "supports": set(),
        "disputes": set(),
    }
    for item_index, item in enumerate(items, start=1):
        item_prefix = f"{prefix}, item {item_index}"
        if not isinstance(item, dict):
            issues.append(f"{item_prefix} must be an object.")
            continue
        stance = item.get("stance")
        url = item.get("url")
        parsed = urlsplit(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            issues.append(f"{item_prefix} needs an HTTP(S) URL.")
        elif stance in stance_hosts:
            stance_hosts[stance].add(parsed.hostname.casefold())
        publisher = item.get("publisher")
        if not isinstance(publisher, str) or not publisher.strip():
            issues.append(f"{item_prefix} needs a publisher.")
        if stance not in STANCES:
            issues.append(f"{item_prefix} needs a valid stance.")
        elif stance in stance_publishers and isinstance(publisher, str):
            stance_publishers[stance].add(publisher.strip().casefold())
        language = item.get("language")
        if language not in LANGUAGES:
            issues.append(f"{item_prefix} needs an EN, VI, or KO language.")
        excerpt = item.get("excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            issues.append(f"{item_prefix} needs an exact evidence excerpt.")
        published_at = item.get("published_at")
        if not isinstance(published_at, str) or not _is_iso_date(published_at):
            issues.append(f"{item_prefix} needs an ISO publication date.")
    if status in {"supported", "mixed"} and (
        len(stance_publishers["supports"]) < 2 or len(stance_hosts["supports"]) < 2
    ):
        issues.append(f"{prefix} needs supporting evidence from two publishers and hosts.")
    if status in {"disputed", "mixed"} and (
        len(stance_publishers["disputes"]) < 2 or len(stance_hosts["disputes"]) < 2
    ):
        issues.append(f"{prefix} needs disputing evidence from two publishers and hosts.")
    independence_note = evidence_set.get("independence_note")
    if not isinstance(independence_note, str) or not independence_note.strip():
        issues.append(f"{prefix} needs an independence note.")
    return issues


def _empty_gold(claim: dict[str, object]) -> bool:
    """True when a claim's gold block still matches the prepared template."""
    gold = claim.get("gold")
    if not isinstance(gold, dict):
        return False
    return not any(
        gold.get(key)
        for key in (
            "expected_status",
            "acceptable_evidence_sets",
            "checked_at",
            "rationale",
            "search_notes",
            "adjudicators",
        )
    )


def split_adjudication(template_path: Path, output_dir: Path) -> dict[str, object]:
    """Create one review workbook per independent adjudicator.

    The packets contain the same hash-bound claims with empty gold scaffolds,
    so two reviewers can record gold labels in parallel without editing one
    shared file. Refuses to split a template that already contains review work.
    """
    data = json.loads(template_path.read_text())
    if data.get("schema_version") != 2:
        raise ValueError("Use adjudication schema version 2.")
    claims = data.get("claims")
    if not isinstance(claims, list) or len(claims) != 30:
        raise ValueError("Split exactly 30 adjudicated claims.")
    candidate_ids = [claim.get("candidate_id") for claim in claims]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("The template contains duplicate claims.")
    for claim in claims:
        if not _empty_gold(claim):
            raise ValueError(
                f"Claim {claim.get('candidate_id')} already contains review work; "
                "prepare a fresh template before splitting."
            )
    reviewers = [
        {"id": "reviewer-a", "role": "independent"},
        {"id": "reviewer-b", "role": "independent"},
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    packets: dict[str, str] = {}
    for reviewer in reviewers:
        packet = {**data, "reviewer": reviewer}
        path = output_dir / f"{reviewer['id']}.json"
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        packets[reviewer["id"]] = str(path)
    return {"packets": packets, "claims": len(claims)}


def merge_adjudication(
    packet_a: Path,
    packet_b: Path,
    template_path: Path,
    output_path: Path,
    selection_path: Path,
) -> dict[str, object]:
    """Merge two completed review workbooks into the canonical gold file.

    Hash-bound claim fields are verified against the prepared template and
    never modified. A packet that is incomplete for any claim stops the merge.
    Disagreements are preserved in `adjudication_notes` with the status left
    unresolved so the validator flags exactly which claims need discussion.
    """
    packets = [(packet_a, "A"), (packet_b, "B")]
    loaded: list[tuple[dict[str, object], str, dict[str, object]]] = []
    for path, label in packets:
        data = json.loads(path.read_text())
        reviewer = data.get("reviewer")
        reviewer_id = (
            reviewer.get("id")
            if isinstance(reviewer, dict) and isinstance(reviewer.get("id"), str)
            else None
        )
        if not reviewer_id or reviewer.get("role") != "independent":
            raise ValueError(f"Packet {label} must declare an independent reviewer.")
        loaded.append((data, reviewer_id, data.get("claims", [])))
    if loaded[0][1] == loaded[1][1]:
        raise ValueError(
            f"Both packets declare the same reviewer ({loaded[0][1]}); "
            "merge requires two distinct independent reviewers."
        )

    template = json.loads(template_path.read_text())
    template_claims = template.get("claims", [])
    if len(template_claims) != 30:
        raise ValueError("The prepared template must contain exactly 30 claims.")

    merged_claims: list[dict[str, object]] = []
    errors: list[str] = []
    disagreements: list[str] = []
    for index, template_claim in enumerate(template_claims):
        candidate_id = template_claim.get("candidate_id")
        packet_golds: list[tuple[str, dict[str, object]]] = []
        for _data, reviewer_id, claims in loaded:
            packet_claim = claims[index]
            for key, expected in template_claim.items():
                if key == "gold":
                    continue
                if packet_claim.get(key) != expected:
                    errors.append(
                        f"Claim {candidate_id} in {reviewer_id}'s packet changed {key}; "
                        "hash-bound fields must stay frozen."
                    )
            gold = packet_claim.get("gold")
            if not isinstance(gold, dict):
                errors.append(f"Claim {candidate_id} in {reviewer_id}'s packet has no gold block.")
                continue
            # Each packet records one reviewer's gold label; the two-reviewer
            # requirement is established by the merge itself.
            issues = [
                issue for issue in _claim_issues(packet_claim) if "adjudicators" not in issue
            ]
            if issues:
                errors.append(
                    f"{reviewer_id} left claim {candidate_id} incomplete: {'; '.join(issues)}"
                )
            packet_golds.append((reviewer_id, gold))
        if errors:
            continue

        gold_a = packet_golds[0][1]
        gold_b = packet_golds[1][1]
        reviewer_a = packet_golds[0][0]
        reviewer_b = packet_golds[1][0]
        status_a = gold_a.get("expected_status")
        status_b = gold_b.get("expected_status")
        notes: list[str] = []
        if status_a == status_b:
            merged_status = status_a
            notes.append(gold_a.get("adjudication_notes") or "")
            notes.append(gold_b.get("adjudication_notes") or "")
            rationale = gold_a.get("rationale")
            search_notes = gold_a.get("search_notes") or ""
            if gold_b.get("search_notes") and gold_b.get("search_notes") != search_notes:
                search_notes = f"{search_notes}\n{reviewer_b}: {gold_b.get('search_notes')}"
        else:
            disagreements.append(str(candidate_id))
            merged_status = None
            rationale = ""
            search_notes = ""
            notes.append(
                f"Reviewers disagree: {reviewer_a} chose {status_a} "
                f"({gold_a.get('rationale')}); {reviewer_b} chose {status_b} "
                f"({gold_b.get('rationale')}). Resolve the disagreement before running."
            )

        merged_claims.append(
            {
                **template_claim,
                "gold": {
                    "expected_status": merged_status,
                    "acceptable_evidence_sets": _union_evidence_sets(
                        gold_a.get("acceptable_evidence_sets"),
                        gold_b.get("acceptable_evidence_sets"),
                    ),
                    "checked_at": max(
                        gold_a.get("checked_at"),
                        gold_b.get("checked_at"),
                        key=lambda value: value or "",
                    ),
                    "rationale": rationale,
                    "search_notes": search_notes,
                    "adjudicators": [
                        {"id": reviewer_a, "role": "independent"},
                        {"id": reviewer_b, "role": "independent"},
                    ],
                    "adjudication_notes": "\n".join(note for note in notes if note),
                },
            }
        )

    if errors:
        raise ValueError("Cannot merge:\n- " + "\n- ".join(errors))

    merged = {
        "schema_version": template.get("schema_version"),
        "selection_sha256": template.get("selection_sha256"),
        "purpose": template.get("purpose"),
        "claims": merged_claims,
    }
    output_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    summary = validate_adjudication(output_path, selection_path)
    return {
        "output": str(output_path),
        "disagreements": disagreements,
        "summary": summary,
    }


def _union_evidence_sets(
    sets_a: object,
    sets_b: object,
) -> list[object]:
    merged: list[object] = []
    seen: set[str] = set()
    for collection in (sets_a, sets_b):
        if not isinstance(collection, list):
            continue
        for evidence_set in collection:
            key = json.dumps(evidence_set, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                merged.append(evidence_set)
    return merged


def _has_timezone(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _is_iso_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True
