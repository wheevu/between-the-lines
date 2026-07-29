import csv
import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from app.evidence_evaluation import LANGUAGES, STATUSES

CONFIDENCE_LEVELS = {"high", "medium", "low"}
REVIEWER_ROLE = "author-ai-assisted"


def validate_author_pilot(
    pilot_path: Path,
    selection_path: Path,
) -> dict[str, object]:
    data = json.loads(pilot_path.read_text())
    claims = data.get("claims", [])
    sources = data.get("sources", [])
    blockers = []

    if data.get("schema_version") != 1:
        blockers.append("Use author pilot schema version 1.")
    expected_selection_hash = sha256(selection_path.read_bytes()).hexdigest()
    if data.get("selection_sha256") != expected_selection_hash:
        blockers.append("The pilot does not match the frozen selection sheet.")

    review = data.get("review")
    if not isinstance(review, dict) or review.get("reviewer_role") != REVIEWER_ROLE:
        blockers.append("Label the review role as author-ai-assisted.")
    elif not _has_timezone(review.get("checked_at")):
        blockers.append("Record a timezone-aware pilot review timestamp.")

    selected = _selected_claims(selection_path)
    candidate_ids = [claim.get("candidate_id") for claim in claims if isinstance(claim, dict)]
    if len(claims) != 30:
        blockers.append("Review exactly 30 selected claims.")
    if len(candidate_ids) != len(set(candidate_ids)):
        blockers.append("Remove duplicate reviewed claims.")
    if set(candidate_ids) != set(selected):
        blockers.append("Review the exact candidate IDs in the frozen selection.")

    language_counts = Counter(
        selected[candidate_id]["source_language"]
        for candidate_id in candidate_ids
        if candidate_id in selected
    )
    if language_counts != Counter({"en": 10, "vi": 10, "ko": 10}):
        blockers.append("Review exactly 10 claims per source language.")

    source_map, source_issues = _validate_sources(sources)
    if source_issues:
        blockers.append("Fix the pilot source library.")

    ready_claims = 0
    claim_issues = []
    status_counts: Counter[str] = Counter()
    for claim in claims:
        if not isinstance(claim, dict):
            claim_issues.append({"candidate_id": None, "issues": ["Claim must be an object."]})
            continue
        issues = _claim_issues(claim, source_map)
        status = claim.get("pilot", {}).get("expected_status")
        if status in STATUSES:
            status_counts[status] += 1
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
        blockers.append("Complete every author pilot status and evidence field.")

    return {
        "claims": len(claims),
        "ready_claims": ready_claims,
        "sources": len(source_map),
        "language_counts": dict(sorted(language_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "source_issues": source_issues,
        "claim_issues": claim_issues,
        "ready_for_author_pilot": not blockers,
        "independent_gold_ready": False,
        "blockers": blockers,
    }


def _selected_claims(selection_path: Path) -> dict[str, dict[str, str]]:
    with selection_path.open(newline="") as source:
        return {
            row["candidate_id"]: row
            for row in csv.DictReader(source)
            if row["include_in_30"].strip().lower() == "yes"
        }


def _validate_sources(
    sources: object,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    if not isinstance(sources, list):
        return {}, [{"source_id": None, "issues": ["Sources must be a list."]}]
    source_map = {}
    source_issues = []
    for source in sources:
        issues = []
        if not isinstance(source, dict):
            source_issues.append({"source_id": None, "issues": ["Source must be an object."]})
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            issues.append("Source needs an ID.")
        elif source_id in source_map:
            issues.append("Source ID must be unique.")
        url = source.get("url")
        parsed = urlsplit(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            issues.append("Source needs an HTTP(S) URL.")
        publisher = source.get("publisher")
        if not isinstance(publisher, str) or not publisher.strip():
            issues.append("Source needs a publisher.")
        if source.get("language") not in LANGUAGES:
            issues.append("Source needs an EN, VI, or KO language.")
        if not _is_iso_date(source.get("published_at")):
            issues.append("Source needs an ISO publication date.")
        excerpt = source.get("excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            issues.append("Source needs an exact evidence excerpt.")
        lineage = source.get("lineage")
        if not isinstance(lineage, str) or not lineage.strip():
            issues.append("Source needs a lineage note.")
        if issues:
            source_issues.append({"source_id": source_id, "issues": issues})
        elif isinstance(source_id, str):
            source_map[source_id] = source
    return source_map, source_issues


def _claim_issues(
    claim: dict[str, object],
    source_map: dict[str, dict[str, object]],
) -> list[str]:
    pilot = claim.get("pilot")
    if not isinstance(pilot, dict):
        return ["Missing pilot object."]
    issues = []
    status = pilot.get("expected_status")
    if status not in STATUSES:
        issues.append("Choose a valid expected status.")
    if pilot.get("confidence") not in CONFIDENCE_LEVELS:
        issues.append("Choose a high, medium, or low confidence.")
    rationale = pilot.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        issues.append("Explain the pilot status.")

    refs_by_stance = {}
    for stance in ("supports", "disputes", "context"):
        refs = pilot.get(stance)
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            issues.append(f"{stance} must be a list of source IDs.")
            refs_by_stance[stance] = []
            continue
        refs_by_stance[stance] = refs
        missing = [ref for ref in refs if ref not in source_map]
        if missing:
            issues.append(f"{stance} contains unknown source IDs: {', '.join(missing)}.")

    supports = refs_by_stance.get("supports", [])
    disputes = refs_by_stance.get("disputes", [])
    if status == "insufficient":
        if supports or disputes:
            issues.append("An insufficient claim cannot have supporting or disputing evidence.")
        search_notes = pilot.get("search_notes")
        if not isinstance(search_notes, str) or not search_notes.strip():
            issues.append("An insufficient claim needs notes describing the search scope.")
    elif status == "supported":
        issues.extend(_independence_issues("supporting", supports, source_map))
        if disputes:
            issues.append("Use mixed when material disputing evidence exists.")
    elif status == "disputed":
        issues.extend(_independence_issues("disputing", disputes, source_map))
        if supports:
            issues.append("Use mixed when material supporting evidence exists.")
    elif status == "mixed":
        issues.extend(_independence_issues("supporting", supports, source_map))
        issues.extend(_independence_issues("disputing", disputes, source_map))
    return issues


def _independence_issues(
    label: str,
    source_ids: list[str],
    source_map: dict[str, dict[str, object]],
) -> list[str]:
    sources = [source_map[source_id] for source_id in source_ids if source_id in source_map]
    publishers = {
        source["publisher"].strip().casefold()
        for source in sources
        if isinstance(source.get("publisher"), str)
    }
    hosts = {
        urlsplit(source["url"]).hostname.casefold()
        for source in sources
        if isinstance(source.get("url"), str) and urlsplit(source["url"]).hostname
    }
    if len(publishers) < 2 or len(hosts) < 2:
        return [f"Use {label} evidence from at least two publishers and hosts."]
    return []


def _has_timezone(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True
