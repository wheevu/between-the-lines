import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from app.models import ClaimCandidate, ClaimCheckResult


@dataclass(frozen=True)
class FrozenEvaluationClaim:
    case_id: str
    source_language: str
    input_url: str
    claim: ClaimCandidate


def load_frozen_claims(
    adjudication_path: Path,
    pool_path: Path,
    corpus_path: Path,
) -> list[FrozenEvaluationClaim]:
    adjudication = json.loads(adjudication_path.read_text())
    pool = json.loads(pool_path.read_text())
    corpus = json.loads(corpus_path.read_text())
    if pool.get("complete") is not True:
        raise ValueError("The frozen claim pool is incomplete.")
    if pool.get("manifest_sha256") != _sha256(corpus_path):
        raise ValueError("The claim pool does not match the frozen corpus.")

    corpus_cases = {case["id"]: case for case in corpus.get("cases", [])}
    candidates = {}
    for case in pool.get("cases", []):
        corpus_case = corpus_cases.get(case.get("id"))
        if corpus_case is None or any(
            case.get(field) != corpus_case.get(field)
            for field in ("source_language", "publisher", "url")
        ):
            raise ValueError("A claim-pool case does not match the frozen corpus.")
        for raw_candidate in case.get("candidates", []):
            candidate = ClaimCandidate.model_validate(raw_candidate)
            if candidate.id in candidates:
                raise ValueError("The frozen claim pool contains duplicate candidate IDs.")
            candidates[candidate.id] = (case, candidate)

    frozen = []
    for gold_claim in adjudication.get("claims", []):
        candidate_id = gold_claim.get("candidate_id")
        matched = candidates.get(candidate_id)
        if matched is None:
            raise ValueError(f"Adjudicated candidate {candidate_id!r} is absent from the pool.")
        case, candidate = matched
        if (
            gold_claim.get("case_id") != case.get("id")
            or gold_claim.get("source_language") != case.get("source_language")
            or gold_claim.get("claim_type") != candidate.claim_type.value
            or gold_claim.get("source_quote") != candidate.source_quote
            or gold_claim.get("standalone_claim") != candidate.standalone_claim
        ):
            raise ValueError(
                f"Adjudicated candidate {candidate.id!r} changed from the frozen pool."
            )
        frozen.append(
            FrozenEvaluationClaim(
                case_id=case["id"],
                source_language=case["source_language"],
                input_url=case["url"],
                claim=candidate,
            )
        )
    if len(frozen) != 30 or len({item.claim.id for item in frozen}) != 30:
        raise ValueError("Run exactly 30 unique adjudicated claims.")
    return frozen


def run_frozen_claims(
    checker,
    claims: list[FrozenEvaluationClaim],
    output_path: Path,
    *,
    identity: dict[str, object],
    max_new_claims: int | None = None,
) -> dict[str, object]:
    if max_new_claims is not None and max_new_claims < 1:
        raise ValueError("max_new_claims must be positive.")
    expected_ids = [item.claim.id for item in claims]
    state = _load_or_create_state(output_path, identity)
    if state.get("complete") is True:
        raise ValueError("The frozen system run is already complete. Move it before rerunning.")

    parsed = {}
    for raw in state.get("claims", []):
        result = ClaimCheckResult.model_validate(raw)
        if result.claim.id in parsed:
            raise ValueError("The partial system run contains duplicate claim IDs.")
        parsed[result.claim.id] = result
    if set(parsed) - set(expected_ids):
        raise ValueError("The partial system run contains claims outside the frozen set.")
    frozen_by_id = {item.claim.id: item for item in claims}
    for candidate_id, result in parsed.items():
        if result.claim != frozen_by_id[candidate_id].claim:
            raise ValueError("A partial system-run claim changed from the frozen pool.")

    state["claims"] = [
        parsed[candidate_id].model_dump(mode="json")
        for candidate_id in expected_ids
        if candidate_id in parsed
    ]
    state["complete"] = False
    state["pause_reason"] = None
    state["stopped_at"] = None
    state["error"] = None
    _write_state(output_path, state)

    processed = 0
    for frozen in claims:
        candidate_id = frozen.claim.id
        if candidate_id in parsed:
            continue
        if max_new_claims is not None and processed >= max_new_claims:
            state["pause_reason"] = "Invocation claim limit reached."
            state["stopped_at"] = candidate_id
            _write_state(output_path, state)
            return state

        started = perf_counter()
        try:
            result = checker.check_claim(
                frozen.claim,
                input_url=frozen.input_url,
            )
        except Exception as error:
            state["stopped_at"] = candidate_id
            state["error"] = f"Unexpected {type(error).__name__} while checking the claim."
            state.setdefault("attempt_failures", []).append(
                {
                    "candidate_id": candidate_id,
                    "failed_at": _now(),
                    "reason": state["error"],
                }
            )
            _write_state(output_path, state)
            return state

        quota_reason = _quota_reason(result)
        if quota_reason:
            state["stopped_at"] = candidate_id
            state["pause_reason"] = quota_reason
            state.setdefault("attempt_failures", []).append(
                {
                    "candidate_id": candidate_id,
                    "failed_at": _now(),
                    "reason": quota_reason,
                }
            )
            _write_state(output_path, state)
            return state

        parsed[candidate_id] = result
        state["claims"].append(result.model_dump(mode="json"))
        state.setdefault("claim_runs", []).append(
            {
                "candidate_id": candidate_id,
                "completed_at": _now(),
                "runtime_ms": round((perf_counter() - started) * 1_000, 1),
            }
        )
        processed += 1
        _write_state(output_path, state)

    state["complete"] = True
    state["generated_at"] = _now()
    _write_state(output_path, state)
    return state


def _load_or_create_state(
    output_path: Path,
    identity: dict[str, object],
) -> dict[str, object]:
    expected = {
        "schema_version": 1,
        "pipeline_version": 1,
        **identity,
    }
    if not output_path.exists():
        return {
            **expected,
            "purpose": (
                "Frozen 30-claim retrieval, local-ranking, and evidence-synthesis run. "
                "Partial checkpoints are not evaluation results."
            ),
            "started_at": _now(),
            "updated_at": _now(),
            "generated_at": None,
            "complete": False,
            "stopped_at": None,
            "pause_reason": None,
            "error": None,
            "claims": [],
            "claim_runs": [],
            "attempt_failures": [],
        }
    state = json.loads(output_path.read_text())
    changed = [field for field, value in expected.items() if state.get(field) != value]
    if changed:
        raise ValueError(
            "The partial system run has different frozen inputs or runtime settings: "
            + ", ".join(changed)
            + "."
        )
    return state


def _write_state(output_path: Path, state: dict[str, object]) -> None:
    state["updated_at"] = _now()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output_path)


def _quota_reason(result: ClaimCheckResult) -> str | None:
    reasons = [
        result.error or "",
        *(failure.reason for failure in result.retrieval_failures),
        *result.assessment.limitations,
    ]
    return next((reason for reason in reasons if "quota is exhausted" in reason.lower()), None)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
