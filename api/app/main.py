from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.analyzer import Analyzer
from app.article import ArticleExtractionError, extract_article
from app.claim_extractor import ClaimExtractor
from app.config import load_settings
from app.evaluation_summary import summarize_database
from app.evidence_retrieval import FactCheckToolsProvider, GoogleSearchProvider
from app.evidence_synthesis import EvidenceClassifier
from app.fact_checker import FactChecker
from app.gemini import GeminiTranslator
from app.local_models import LocalModels
from app.models import (
    AnalysisCreate,
    AnalysisJob,
    AnalysisStatus,
    ClaimSelection,
    ExtractedArticle,
    ExtractRequest,
    FactCheckFeedbackCreate,
    FactCheckFeedbackRecord,
    FactCheckFeedbackTarget,
    FactCheckJob,
    FactCheckStatus,
    FeedbackCreate,
    FeedbackRecord,
)
from app.query_generator import QueryGenerator
from app.store import Store

settings = load_settings()
store = Store(settings.database_path)
local_models = LocalModels(settings.embedding_backend)
analyzer = Analyzer(
    settings=settings,
    store=store,
    gemini=GeminiTranslator(settings.gemini_api_key, settings.gemini_model),
)
claim_extractor = ClaimExtractor(
    store=store,
    api_key=settings.gemini_api_key,
    model=settings.gemini_model,
)
fact_checker = FactChecker(
    settings=settings,
    store=store,
    query_generator=QueryGenerator(
        settings.gemini_api_key,
        settings.gemini_model,
    ),
    fact_check_provider=FactCheckToolsProvider(settings.fact_check_api_key),
    search_provider=GoogleSearchProvider(settings.gemini_api_key, settings.gemini_model),
    local_models=local_models,
    classifier=EvidenceClassifier(settings.gemini_api_key, settings.gemini_model),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    yield


app = FastAPI(title="Between the Lines API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_claim_trace() -> None:
    if not settings.claim_trace_enabled:
        raise HTTPException(status_code=404, detail="Claim Trace is disabled on this server.")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/extract", response_model=ExtractedArticle)
def extract(request: ExtractRequest) -> ExtractedArticle:
    try:
        return extract_article(str(request.url), settings)
    except ArticleExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/analyses", response_model=AnalysisJob, status_code=202)
def create_analysis(request: AnalysisCreate, tasks: BackgroundTasks) -> AnalysisJob:
    job = store.create_analysis()
    tasks.add_task(analyzer.run, job.id, request)
    return job


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisJob)
def get_analysis(analysis_id: str) -> AnalysisJob:
    job = store.get_analysis(analysis_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return job


@app.post("/api/analyses/{analysis_id}/feedback", response_model=FeedbackRecord)
def add_feedback(analysis_id: str, feedback: FeedbackCreate) -> FeedbackRecord:
    if store.get_analysis(analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return store.add_feedback(analysis_id, feedback)


@app.post(
    "/api/analyses/{analysis_id}/fact-checks",
    response_model=FactCheckJob,
    status_code=202,
)
def create_fact_check(analysis_id: str, tasks: BackgroundTasks) -> FactCheckJob:
    require_claim_trace()
    analysis = store.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if analysis.status is not AnalysisStatus.COMPLETE or analysis.result is None:
        raise HTTPException(
            status_code=409,
            detail="Finish the article analysis before choosing claims.",
        )
    job, created = store.create_or_get_fact_check(analysis_id)
    if created:
        tasks.add_task(claim_extractor.run, job.id)
    return job


@app.get("/api/fact-checks/{fact_check_id}", response_model=FactCheckJob)
def get_fact_check(fact_check_id: str) -> FactCheckJob:
    require_claim_trace()
    job = store.get_fact_check(fact_check_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Fact check not found.")
    return job


@app.post(
    "/api/fact-checks/{fact_check_id}/feedback",
    response_model=FactCheckFeedbackRecord,
)
def add_fact_check_feedback(
    fact_check_id: str,
    feedback: FactCheckFeedbackCreate,
) -> FactCheckFeedbackRecord:
    require_claim_trace()
    job = store.get_fact_check(fact_check_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Fact check not found.")
    if job.result is None:
        raise HTTPException(
            status_code=409,
            detail="Evidence results aren't ready for feedback.",
        )
    claim_ids = {claim_result.claim.id for claim_result in job.result.claims}
    evidence_ids = {
        evidence.id for claim_result in job.result.claims for evidence in claim_result.evidence
    }
    valid_ids = (
        evidence_ids if feedback.target_type is FactCheckFeedbackTarget.EVIDENCE else claim_ids
    )
    if feedback.target_id not in valid_ids:
        raise HTTPException(
            status_code=422,
            detail="Choose an item from this evidence result.",
        )
    return store.add_fact_check_feedback(fact_check_id, feedback)


@app.post("/api/fact-checks/{fact_check_id}/selection", response_model=FactCheckJob)
def select_fact_check_claims(
    fact_check_id: str,
    selection: ClaimSelection,
    tasks: BackgroundTasks,
) -> FactCheckJob:
    require_claim_trace()
    job = store.get_fact_check(fact_check_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Fact check not found.")
    active_statuses = {
        FactCheckStatus.RETRIEVING,
        FactCheckStatus.RANKING,
        FactCheckStatus.ALIGNING,
        FactCheckStatus.SYNTHESIZING,
        FactCheckStatus.COMPLETE,
    }
    if job.status in active_statuses:
        if job.selected_candidate_ids == selection.candidate_ids:
            return job
        raise HTTPException(
            status_code=409,
            detail="This evidence check already started with different claims.",
        )
    if job.status not in {
        FactCheckStatus.AWAITING_SELECTION,
        FactCheckStatus.FAILED,
    }:
        raise HTTPException(status_code=409, detail="Claims aren't ready for selection.")

    candidate_by_id = {candidate.id: candidate for candidate in job.candidates}
    selected = [candidate_by_id.get(candidate_id) for candidate_id in selection.candidate_ids]
    if any(candidate is None for candidate in selected):
        raise HTTPException(status_code=422, detail="Choose claims from this article.")
    if any(candidate.claim_type.value == "unsuitable" for candidate in selected if candidate):
        raise HTTPException(
            status_code=422,
            detail="Opinion or prediction claims can't be checked across sources.",
        )

    readiness = summarize_database(store.path)
    if readiness["ready_for_evidence_layer_decision"]:
        store.update_fact_check(
            fact_check_id,
            status=FactCheckStatus.RETRIEVING,
            stage="Preparing multilingual evidence searches",
            progress=5,
            selected_candidate_ids=selection.candidate_ids,
        )
        tasks.add_task(fact_checker.run, fact_check_id)
    else:
        store.update_fact_check(
            fact_check_id,
            status=FactCheckStatus.AWAITING_SELECTION,
            stage="Claims saved; evidence search is waiting for translation review",
            progress=100,
            selected_candidate_ids=selection.candidate_ids,
        )
    updated = store.get_fact_check(fact_check_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Fact check not found.")
    return updated
