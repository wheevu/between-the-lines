import argparse
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from app.claim_trace import assign_source_lineages, build_trace_summary
from app.config import load_settings
from app.evidence_retrieval import (
    FactCheckToolsProvider,
    GoogleSearchProvider,
    retrieve_pages,
)
from app.evidence_synthesis import EvidenceClassifier, EvidenceSynthesisError, assess_claim
from app.fact_checker import FactChecker
from app.local_models import LocalModels
from app.models import (
    ClaimCandidate,
    ClaimFacets,
    ClaimModality,
    ClaimType,
    DiscoveredSource,
    DiscoveryMethod,
    Language,
    SourceType,
)
from app.query_generator import QueryGenerator
from app.store import Store

API_DIR = Path(__file__).parents[1]
MANIFEST = API_DIR / "evaluation" / "claim-trace-corpus.json"
DEFAULT_OUTPUT = API_DIR / "evaluation" / "claim-trace-closed-set-pilot.json"
FULL_OUTPUT = API_DIR / "evaluation" / "claim-trace-closed-set-full.json"
NUMBER = re.compile(r"(?<!\d)\d[\d.,–-]*(?:\s*%)?")
PILOT_CASES = {
    "vietnam-ai-law-ko-core": {
        "claim_type": ClaimType.FACT,
        "modality": ClaimModality.ASSERTED,
        "attribution": None,
    },
    "hanta-en-risk": {
        "claim_type": ClaimType.ATTRIBUTED,
        "modality": ClaimModality.ASSERTED,
        "attribution": "WHO",
    },
    "wmo-vi-probability": {
        "claim_type": ClaimType.ATTRIBUTED,
        "modality": ClaimModality.FUTURE,
        "attribution": "WMO",
    },
    "nvidia-en-announcement": {
        "claim_type": ClaimType.FACT,
        "modality": ClaimModality.ASSERTED,
        "attribution": None,
    },
    "qs-ko-unist": {
        "claim_type": ClaimType.FACT,
        "modality": ClaimModality.ASSERTED,
        "attribution": None,
    },
    "world-cup-vi-result": {
        "claim_type": ClaimType.FACT,
        "modality": ClaimModality.ASSERTED,
        "attribution": None,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Run frozen Claim Trace cases against their known cross-language source sets.")
    )
    parser.add_argument("--suite", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum new cases to process; defaults to the complete selected suite.",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    cases = load_cases(manifest, args.suite)
    limit = args.limit if args.limit is not None else len(cases)
    if not 1 <= limit <= len(cases):
        parser.error(f"--limit must be between 1 and {len(cases)} for {args.suite}")
    output = args.output or (DEFAULT_OUTPUT if args.suite == "pilot" else FULL_OUTPUT)
    corpus_sha256 = sha256(MANIFEST.read_bytes()).hexdigest()
    state = _load_state(
        output,
        corpus_sha256,
        [case["id"] for case in cases],
        purpose=(
            f"{len(cases)}-case Claim Trace {args.suite} using frozen, known "
            "cross-language source triples. Discovery is intentionally excluded so "
            "alignment and source-lineage handling can be evaluated separately from "
            "search availability."
        ),
    )
    completed_ids = {result["case_id"] for result in state["results"]}
    settings = load_settings()
    local_models = LocalModels(settings.embedding_backend)
    checker = FactChecker(
        settings=settings,
        store=Store(settings.database_path),
        query_generator=QueryGenerator(
            settings.gemini_api_key,
            settings.gemini_model,
        ),
        fact_check_provider=FactCheckToolsProvider(settings.fact_check_api_key),
        search_provider=GoogleSearchProvider(
            settings.gemini_api_key,
            settings.gemini_model,
        ),
        local_models=local_models,
        classifier=EvidenceClassifier(
            settings.gemini_api_key,
            settings.gemini_model,
        ),
    )

    processed = 0
    for case in cases:
        if case["id"] in completed_ids:
            continue
        if processed >= limit:
            state["stopped_at"] = case["id"]
            state["pause_reason"] = "Invocation case limit reached."
            _write_state(output, state)
            return 2

        started = perf_counter()
        claim = _claim(case)
        source_article = case["source_article"]
        sources = [
            _discovered_source(article)
            for article in case["event"]["articles"]
            if article["id"] != source_article["id"]
        ]
        batch = retrieve_pages(
            sources,
            input_url=source_article["url"],
            settings=settings,
        )
        evidence = checker._rank_evidence(claim.standalone_claim, batch)
        try:
            evidence = checker.classifier.classify(claim, evidence)
        except EvidenceSynthesisError as error:
            state["stopped_at"] = case["id"]
            state["pause_reason"] = str(error)
            _write_state(output, state)
            return 2
        evidence = assign_source_lineages(evidence, local_models)
        assessment = assess_claim(claim, evidence)
        trace = build_trace_summary(assessment, evidence)
        state["results"].append(
            {
                "case_id": case["id"],
                "topic": case["event"]["topic"],
                "profile": case["event"]["profile"],
                "source_article_id": source_article["id"],
                "source_language": case["seed_language"],
                "claim": claim.model_dump(mode="json"),
                "runtime_seconds": round(perf_counter() - started, 3),
                "assessment": assessment.model_dump(mode="json"),
                "trace": trace.model_dump(mode="json"),
                "evidence": [_evidence_summary(item) for item in evidence],
                "retrieval_failures": [
                    failure.model_dump(mode="json") for failure in batch.failures
                ],
            }
        )
        processed += 1
        _write_state(output, state)

    state["complete"] = True
    state["generated_at"] = _now()
    state["stopped_at"] = None
    state["pause_reason"] = None
    state["summary"] = _summarize(state["results"])
    _write_state(output, state)
    print(json.dumps(state["summary"], ensure_ascii=False, indent=2))
    return 0


def load_cases(manifest: dict, suite: str) -> list[dict]:
    if suite not in {"pilot", "full"}:
        raise ValueError(f"Unknown closed-set suite: {suite}")
    cases = []
    for event in manifest["events"]:
        for trace_case in event["trace_cases"]:
            if suite == "pilot" and trace_case["id"] not in PILOT_CASES:
                continue
            source_article = next(
                article
                for article in event["articles"]
                if article["source_language"] == trace_case["seed_language"]
            )
            cases.append(
                {
                    **trace_case,
                    "event": event,
                    "source_article": source_article,
                }
            )
    if suite == "pilot":
        order = {case_id: index for index, case_id in enumerate(PILOT_CASES)}
        cases.sort(key=lambda case: order[case["id"]])
    expected = (
        len(PILOT_CASES)
        if suite == "pilot"
        else sum(len(event["trace_cases"]) for event in manifest["events"])
    )
    if len(cases) != expected:
        raise ValueError("The frozen corpus is missing a closed-set pilot case.")
    return cases


def load_pilot_cases(manifest: dict) -> list[dict]:
    return load_cases(manifest, "pilot")


def _claim(case: dict) -> ClaimCandidate:
    settings = PILOT_CASES.get(
        case["id"],
        {
            "claim_type": ClaimType.FACT,
            "modality": ClaimModality.ASSERTED,
            "attribution": None,
        },
    )
    claim_text = case["seed_claim"]
    numbers = list(dict.fromkeys(match.group(0).strip() for match in NUMBER.finditer(claim_text)))
    return ClaimCandidate(
        id=f"closed-{case['id']}",
        source_quote=claim_text,
        segment_ids=["frozen-benchmark-claim"],
        standalone_claim=claim_text,
        claim_type=settings["claim_type"],
        entities=[],
        dates=[],
        numbers=numbers,
        facets=ClaimFacets(
            attribution=settings["attribution"],
            modality=settings["modality"],
        ),
        reason=(
            "Human-frozen benchmark proposition for cross-language alignment; "
            "claim extraction is evaluated separately."
        ),
        source_language=Language(case["seed_language"]),
    )


def _discovered_source(article: dict) -> DiscoveredSource:
    return DiscoveredSource(
        url=article["url"],
        title=article["title"],
        publisher=article["publisher"],
        language=Language(article["source_language"]),
        source_type=SourceType.WEB,
        discovery_method=DiscoveryMethod.GOOGLE_SEARCH,
    )


def _evidence_summary(item) -> dict:
    return {
        "id": item.id,
        "url": item.url,
        "title": item.title,
        "publisher": item.publisher,
        "language": item.language.value,
        "published_at": item.published_at,
        "source_type": item.source_type.value,
        "direct": item.direct,
        "stance": item.stance.value if item.stance else None,
        "stance_reason": item.stance_reason,
        "alignment_state": item.alignment_state.value,
        "aligned_quote": item.aligned_quote,
        "meaning_deltas": [delta.model_dump(mode="json") for delta in item.meaning_deltas],
        "credited_origin": item.credited_origin,
        "cluster_id": item.cluster_id,
        "mismatch": item.mismatch,
    }


def _summarize(results: list[dict]) -> dict:
    return {
        "cases": len(results),
        "topics": sorted({result["topic"] for result in results}),
        "languages": {
            language: sum(result["source_language"] == language for result in results)
            for language in ("en", "ko", "vi")
        },
        "evidence_states": {
            state: sum(result["trace"]["evidence_state"] == state for result in results)
            for state in ("corroborated", "conflicting", "unresolved")
        },
        "aligned_items": sum(
            item["alignment_state"] == "aligned"
            for result in results
            for item in result["evidence"]
        ),
        "meaning_deltas": sum(
            len(item["meaning_deltas"]) for result in results for item in result["evidence"]
        ),
        "article_text_stored": False,
        "search_discovery_used": False,
    }


def _load_state(
    output: Path,
    corpus_sha256: str,
    case_ids: list[str],
    *,
    purpose: str | None = None,
) -> dict:
    expected = {
        "schema_version": 1,
        "corpus_sha256": corpus_sha256,
        "case_ids": case_ids,
    }
    if output.exists():
        state = json.loads(output.read_text())
        if any(state.get(key) != value for key, value in expected.items()):
            raise ValueError("The partial pilot does not match the frozen corpus.")
        if state.get("complete"):
            raise ValueError("The closed-set pilot is already complete.")
        return state
    return {
        **expected,
        "purpose": purpose
        or (
            "Six-topic Claim Trace pilot using frozen, known cross-language source triples. "
            "Discovery is intentionally excluded so alignment and lineage can be evaluated "
            "separately from search availability."
        ),
        "started_at": _now(),
        "updated_at": _now(),
        "generated_at": None,
        "complete": False,
        "stopped_at": None,
        "pause_reason": None,
        "results": [],
    }


def _write_state(output: Path, state: dict) -> None:
    state["updated_at"] = _now()
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output)


def _now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
