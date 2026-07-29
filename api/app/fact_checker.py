import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlsplit

from app.claim_trace import assign_source_lineages, build_trace_summary
from app.config import Settings
from app.evidence_ranker import EvidencePassage, chunk_text, rank_passages
from app.evidence_retrieval import (
    EvidenceDiscoveryError,
    FactCheckToolsProvider,
    GoogleSearchProvider,
    RetrievalBatch,
    RetrievedPage,
    retrieve_pages,
)
from app.evidence_synthesis import (
    EvidenceClassifier,
    EvidenceSynthesisError,
    assess_claim,
)
from app.language_detection import detect_language as _detect_language
from app.local_models import LocalModels
from app.models import (
    ClaimAssessment,
    ClaimCandidate,
    ClaimCheckResult,
    ClaimEvidenceStatus,
    DiscoveredSource,
    EvidenceItem,
    EvidenceSourceKind,
    FactCheckResult,
    FactCheckStatus,
    RetrievalFailure,
    SourceType,
)
from app.query_generator import QueryGenerationError, QueryGenerator
from app.store import Store

WORDS = re.compile(r"\w+", re.UNICODE)
LOGGER = logging.getLogger(__name__)


class FactChecker:
    def __init__(
        self,
        *,
        settings: Settings,
        store: Store,
        query_generator: QueryGenerator,
        fact_check_provider: FactCheckToolsProvider,
        search_provider: GoogleSearchProvider,
        local_models: LocalModels,
        classifier: EvidenceClassifier,
    ) -> None:
        self.settings = settings
        self.store = store
        self.query_generator = query_generator
        self.fact_check_provider = fact_check_provider
        self.search_provider = search_provider
        self.local_models = local_models
        self.classifier = classifier

    def run(self, fact_check_id: str) -> None:
        job = self.store.get_fact_check(fact_check_id)
        if job is None:
            return
        analysis = self.store.get_analysis(job.analysis_id)
        if analysis is None or analysis.result is None:
            self._fail(fact_check_id, "The article analysis is no longer available.")
            return
        candidate_by_id = {candidate.id: candidate for candidate in job.candidates}
        selected = [
            candidate_by_id[candidate_id]
            for candidate_id in job.selected_candidate_ids
            if candidate_id in candidate_by_id
        ]
        if not selected:
            self._fail(fact_check_id, "No selected claims were available.")
            return

        completed: list[ClaimCheckResult] = []
        try:
            for index, claim in enumerate(selected):
                claim_number = index + 1
                claim_total = len(selected)

                def update_stage(
                    status: FactCheckStatus,
                    fraction: float,
                    *,
                    number: int = claim_number,
                    total: int = claim_total,
                ) -> None:
                    labels = {
                        FactCheckStatus.RANKING: "Ranking related reporting",
                        FactCheckStatus.ALIGNING: "Tracing the claim across languages",
                        FactCheckStatus.SYNTHESIZING: "Summarizing agreements and differences",
                    }
                    self.store.update_fact_check(
                        fact_check_id,
                        status=status,
                        stage=f"{labels[status]} for claim {number} of {total}",
                        progress=_claim_progress(number, total, fraction),
                    )

                self.store.update_fact_check(
                    fact_check_id,
                    status=FactCheckStatus.RETRIEVING,
                    stage=f"Finding evidence for claim {claim_number} of {claim_total}",
                    progress=_claim_progress(claim_number, claim_total, 0),
                    result=FactCheckResult(claims=completed, checked_at=_now()),
                )
                completed.append(
                    self.check_claim(
                        claim,
                        input_url=analysis.result.source_url,
                        on_stage=update_stage,
                    )
                )
            self.store.update_fact_check(
                fact_check_id,
                status=FactCheckStatus.COMPLETE,
                stage="Evidence ready to inspect",
                progress=100,
                result=FactCheckResult(claims=completed, checked_at=_now()),
            )
        except Exception:
            LOGGER.exception("Fact-check worker failed for job %s", fact_check_id)
            self.store.update_fact_check(
                fact_check_id,
                status=FactCheckStatus.FAILED,
                stage="Evidence check stopped",
                progress=100,
                result=FactCheckResult(claims=completed, checked_at=_now()),
                error="Evidence checking stopped unexpectedly. Try again.",
            )

    def check_claim(
        self,
        claim: ClaimCandidate,
        *,
        input_url: str | None,
        on_stage: Callable[[FactCheckStatus, float], None] | None = None,
    ) -> ClaimCheckResult:
        failures: list[RetrievalFailure] = []
        try:
            queries = self.query_generator.generate(claim)
        except QueryGenerationError as error:
            return _unresolved_claim(claim, str(error))

        discovered: list[DiscoveredSource] = []
        for query in queries:
            try:
                discovered.extend(self.fact_check_provider.search(query))
            except EvidenceDiscoveryError as error:
                failures.append(RetrievalFailure(reason=str(error)))
                break
        try:
            discovered.extend(self.search_provider.discover(queries))
        except EvidenceDiscoveryError as error:
            failures.append(RetrievalFailure(reason=str(error)))

        batch = retrieve_pages(
            discovered,
            input_url=input_url,
            settings=self.settings,
        )
        failures.extend(batch.failures)
        if on_stage:
            on_stage(FactCheckStatus.RANKING, 0.55)
        evidence = self._rank_evidence(claim.standalone_claim, batch)
        if evidence:
            if on_stage:
                on_stage(FactCheckStatus.ALIGNING, 0.72)
            try:
                evidence = self.classifier.classify(claim, evidence)
                evidence = assign_source_lineages(evidence, self.local_models)
            except EvidenceSynthesisError as error:
                failures.append(RetrievalFailure(reason=str(error)))
        if on_stage:
            on_stage(FactCheckStatus.SYNTHESIZING, 0.9)
        assessment = assess_claim(claim, evidence)
        if failures:
            assessment = assessment.model_copy(
                update={
                    "limitations": [
                        *assessment.limitations,
                        "Some discovery, page-reading, or comparison steps were unavailable.",
                    ]
                }
            )
        return ClaimCheckResult(
            claim=claim,
            queries=queries,
            evidence=evidence,
            assessment=assessment,
            trace=build_trace_summary(assessment, evidence),
            retrieval_failures=failures,
        )

    def _rank_evidence(
        self,
        claim_text: str,
        batch: RetrievalBatch,
    ) -> list[EvidenceItem]:
        items = _evidence_items(batch.pages)
        passage_by_id = {
            item.id: EvidencePassage(
                id=item.id,
                text=item.excerpt,
                publisher=item.publisher,
                cluster_id=item.cluster_id,
            )
            for item in items
        }
        ranked = rank_passages(
            claim_text,
            list(passage_by_id.values())[:80],
            self.local_models,
            limit=6,
        )
        item_by_id = {item.id: item for item in items}
        return [
            item_by_id[result.passage.id].model_copy(update={"relevance": result.relevance})
            for result in ranked
        ]

    def _fail(self, fact_check_id: str, message: str) -> None:
        self.store.update_fact_check(
            fact_check_id,
            status=FactCheckStatus.FAILED,
            stage="Evidence check stopped",
            progress=100,
            error=message,
        )


def _evidence_items(pages: list[RetrievedPage]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    cluster_excerpts: list[tuple[str, str]] = []
    for page in pages:
        language = _detect_language(page.text)
        for index, excerpt in enumerate(chunk_text(page.text, language)):
            digest = sha256(f"{page.url}\0{index}\0{excerpt}".encode()).hexdigest()[:12]
            content_hash = sha256(excerpt.encode()).hexdigest()
            cluster_id = _near_duplicate_cluster(excerpt, content_hash, cluster_excerpts)
            cluster_excerpts.append((cluster_id, excerpt))
            items.append(
                EvidenceItem(
                    id=f"evidence-{digest}",
                    url=page.url,
                    title=page.title or page.source.title,
                    publisher=page.source.publisher,
                    publisher_key=urlsplit(page.url).hostname,
                    language=language,
                    excerpt=excerpt,
                    source_type=(
                        EvidenceSourceKind.PROFESSIONAL_FACT_CHECK
                        if page.source.source_type is SourceType.FACT_CHECK
                        else EvidenceSourceKind.SECONDARY_COMMENTARY
                    ),
                    rating=page.source.rating,
                    published_at=page.published_at,
                    retrieved_at=_now(),
                    content_hash=content_hash,
                    cluster_id=cluster_id,
                    relevance=0,
                )
            )
            if len(items) == 80:
                return items
    return items


def _near_duplicate_cluster(
    excerpt: str,
    fallback: str,
    previous: list[tuple[str, str]],
) -> str:
    tokens = set(WORDS.findall(excerpt.lower()))
    if not tokens:
        return fallback
    for cluster_id, other in previous:
        other_tokens = set(WORDS.findall(other.lower()))
        union = tokens | other_tokens
        intersection = tokens & other_tokens
        containment = len(intersection) / min(len(tokens), len(other_tokens))
        jaccard = len(intersection) / len(union) if union else 0
        if containment >= 0.9 and jaccard >= 0.6:
            return cluster_id
    return fallback


def _unresolved_claim(claim, error: str) -> ClaimCheckResult:
    return ClaimCheckResult(
        claim=claim,
        assessment=ClaimAssessment(
            claim_id=claim.id,
            status=ClaimEvidenceStatus.INSUFFICIENT,
            explanation="Evidence search could not be completed for this claim.",
            limitations=[error],
        ),
        error=error,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _claim_progress(number: int, total: int, fraction: float) -> int:
    claim_span = 80 / total
    return int(15 + ((number - 1) + fraction) * claim_span)
