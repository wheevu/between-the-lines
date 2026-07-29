from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Language(StrEnum):
    ENGLISH = "en"
    VIETNAMESE = "vi"
    KOREAN = "ko"


LANGUAGE_NAMES = {
    Language.ENGLISH: "English",
    Language.VIETNAMESE: "Vietnamese",
    Language.KOREAN: "Korean",
}


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    TRANSLATING = "translating"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class FlagKind(StrEnum):
    MEANING_RISK = "meaning-risk"
    CULTURAL_NOTE = "cultural-note"
    UNCERTAIN = "uncertain"


class AmbiguityCategory(StrEnum):
    NEGATION = "negation"
    MODALITY = "modality"
    ATTRIBUTION = "attribution"
    SCOPE = "scope"
    NUMBER = "number"
    DATE = "date"
    ENTITY = "entity"
    INFORMATION_LOSS = "information-loss"
    IDIOM = "idiom"
    HONORIFIC = "honorific"
    CULTURAL_CONTEXT = "cultural-context"
    LEXICAL = "lexical"
    MODEL_DISAGREEMENT = "model-disagreement"


class ExtractRequest(BaseModel):
    url: HttpUrl


class ExtractedArticle(BaseModel):
    url: str
    title: str | None = None
    published_at: str | None = None
    text: str


class AnalysisCreate(BaseModel):
    source_language: Language
    target_language: Language | None = None
    text: str | None = None
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_one_input(self) -> "AnalysisCreate":
        if bool(self.text and self.text.strip()) == bool(self.url):
            raise ValueError("Provide either article text or a URL.")
        if self.target_language is self.source_language:
            raise ValueError("Choose a target language different from the article language.")
        return self


class GeminiNote(BaseModel):
    source_quote: str
    translation_quote: str
    category: AmbiguityCategory
    explanation: str
    alternative: str | None = None


class GeminiTranslation(BaseModel):
    segment_id: str
    translation: str
    notes: list[GeminiNote] = Field(default_factory=list)


class GeminiBatch(BaseModel):
    translations: list[GeminiTranslation]


class AmbiguityFlag(BaseModel):
    id: str
    target_language: Language
    kind: FlagKind
    category: AmbiguityCategory
    confidence: Literal["high", "medium"] | None = None
    source_quote: str
    translation_quote: str | None = None
    explanation: str
    alternative: str | None = None
    signals: list[str] = Field(default_factory=list)


class TargetTranslation(BaseModel):
    language: Language
    text: str
    shadow_text: str | None = None
    similarity: float | None = None
    back_translation_similarity: float | None = None
    flags: list[AmbiguityFlag] = Field(default_factory=list)


class SegmentResult(BaseModel):
    id: str
    paragraph_index: int
    sentence_index: int
    source_text: str
    translations: list[TargetTranslation]


class AnalysisResult(BaseModel):
    source_language: Language
    source_title: str | None = None
    source_url: str | None = None
    segments: list[SegmentResult]


class AnalysisJob(BaseModel):
    id: str
    status: AnalysisStatus
    stage: str
    progress: Annotated[int, Field(ge=0, le=100)]
    result: AnalysisResult | None = None
    error: str | None = None


class FeedbackVerdict(StrEnum):
    HELPFUL = "helpful"
    INCORRECT = "incorrect"
    UNSURE = "unsure"


class ReviewerRole(StrEnum):
    AUTHOR = "author"
    INDEPENDENT = "independent"
    UNSPECIFIED = "unspecified"


class FeedbackCreate(BaseModel):
    flag_id: str
    verdict: FeedbackVerdict
    correction: str | None = Field(default=None, max_length=1_000)
    reviewer_role: ReviewerRole = ReviewerRole.UNSPECIFIED


class FeedbackRecord(FeedbackCreate):
    id: str
    analysis_id: str


class FactCheckStatus(StrEnum):
    EXTRACTING_CLAIMS = "extracting_claims"
    AWAITING_SELECTION = "awaiting_selection"
    RETRIEVING = "retrieving"
    RANKING = "ranking"
    ALIGNING = "aligning"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"


class ClaimType(StrEnum):
    FACT = "fact"
    ATTRIBUTED = "attributed"
    UNSUITABLE = "unsuitable"


class ClaimModality(StrEnum):
    ASSERTED = "asserted"
    UNCERTAIN = "uncertain"
    FUTURE = "future"
    DENIED = "denied"


class LegalState(StrEnum):
    ALLEGATION = "allegation"
    INVESTIGATION = "investigation"
    FILING = "filing"
    RULING = "ruling"
    FINDING = "finding"


class ClaimFacets(BaseModel):
    attribution: str | None = None
    modality: ClaimModality = ClaimModality.ASSERTED
    legal_state: LegalState | None = None


class GeminiClaimCandidate(BaseModel):
    source_quote: str
    segment_ids: list[str] = Field(min_length=1)
    standalone_claim: str
    claim_type: ClaimType
    entities: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    facets: ClaimFacets = Field(default_factory=ClaimFacets)
    reason: str


class GeminiClaimBatch(BaseModel):
    candidates: list[GeminiClaimCandidate] = Field(min_length=1, max_length=5)


class ClaimCandidate(GeminiClaimCandidate):
    id: str
    source_language: Language | None = None


class SearchQuery(BaseModel):
    language: Language
    exact_query: str = Field(min_length=1, max_length=240)
    context_query: str = Field(min_length=1, max_length=240)
    challenge_query: str | None = Field(default=None, min_length=1, max_length=240)


class GeminiQueryBatch(BaseModel):
    queries: list[SearchQuery] = Field(min_length=3, max_length=3)


class SourceType(StrEnum):
    FACT_CHECK = "fact-check"
    WEB = "web"


class DiscoveryMethod(StrEnum):
    FACT_CHECK_TOOLS = "fact-check-tools"
    GOOGLE_SEARCH = "google-search"


class DiscoveredSource(BaseModel):
    url: str
    title: str | None = None
    publisher: str
    language: Language | None = None
    source_type: SourceType
    discovery_method: DiscoveryMethod
    rating: str | None = None


class RetrievalFailure(BaseModel):
    url: str | None = None
    reason: str


class EvidenceStance(StrEnum):
    SUPPORTS = "supports"
    DISPUTES = "disputes"
    CONTEXT = "context"
    IRRELEVANT = "irrelevant"


class AlignmentState(StrEnum):
    ALIGNED = "aligned"
    PARTIAL = "partial"
    NOT_ALIGNED = "not-aligned"
    UNCERTAIN = "uncertain"


class MeaningDeltaType(StrEnum):
    CERTAINTY = "certainty"
    SCOPE = "scope"
    ATTRIBUTION = "attribution"
    NUMBER = "number"
    DATE = "date"
    LEGAL_STATE = "legal-state"
    CONTEXT = "context"


class MeaningDelta(BaseModel):
    type: MeaningDeltaType
    description: str = Field(min_length=1, max_length=300)


class EvidenceSourceKind(StrEnum):
    PRIMARY = "primary"
    PROFESSIONAL_FACT_CHECK = "professional-fact-check"
    DIRECT_REPORTING = "direct-reporting"
    SECONDARY_COMMENTARY = "secondary-commentary"


class EvidenceItem(BaseModel):
    id: str
    url: str
    title: str | None = None
    publisher: str
    publisher_key: str | None = None
    language: Language
    excerpt: str
    source_type: EvidenceSourceKind
    rating: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    content_hash: str
    cluster_id: str
    relevance: float
    stance: EvidenceStance | None = None
    stance_reason: str | None = None
    direct: bool | None = None
    mismatch: str | None = None
    aligned_quote: str | None = None
    alignment_state: AlignmentState = AlignmentState.UNCERTAIN
    meaning_deltas: list[MeaningDelta] = Field(default_factory=list)
    credited_origin: str | None = None


class GeminiEvidenceStance(BaseModel):
    evidence_id: str
    stance: EvidenceStance
    reason: str
    direct: bool
    source_type: EvidenceSourceKind
    mismatch: str | None = None
    aligned_quote: str | None = None
    alignment_state: AlignmentState = AlignmentState.UNCERTAIN
    meaning_deltas: list[MeaningDelta] = Field(default_factory=list)
    credited_origin: str | None = None


class GeminiStanceBatch(BaseModel):
    evidence: list[GeminiEvidenceStance]


class ClaimEvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    DISPUTED = "disputed"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"


class ClaimAssessment(BaseModel):
    claim_id: str
    status: ClaimEvidenceStatus
    explanation: str
    support_evidence_ids: list[str] = Field(default_factory=list)
    challenge_evidence_ids: list[str] = Field(default_factory=list)
    context_evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TraceEvidenceState(StrEnum):
    CORROBORATED = "corroborated"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"


class ClaimTraceSummary(BaseModel):
    evidence_state: TraceEvidenceState
    article_count: int = Field(ge=0)
    independent_lineages: int = Field(ge=0)
    languages: list[Language] = Field(default_factory=list)
    meaning_deltas: list[MeaningDelta] = Field(default_factory=list)


class ClaimCheckResult(BaseModel):
    claim: ClaimCandidate
    queries: list[SearchQuery] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    assessment: ClaimAssessment
    trace: ClaimTraceSummary | None = None
    retrieval_failures: list[RetrievalFailure] = Field(default_factory=list)
    error: str | None = None


class FactCheckResult(BaseModel):
    claims: list[ClaimCheckResult] = Field(default_factory=list)
    checked_at: str


class FactCheckFeedbackTarget(StrEnum):
    EVIDENCE = "evidence"
    STATUS = "status"


class FactCheckFeedbackCreate(BaseModel):
    target_type: FactCheckFeedbackTarget
    target_id: str = Field(min_length=1, max_length=200)
    verdict: FeedbackVerdict
    correction: str | None = Field(default=None, max_length=1_000)
    better_source_url: HttpUrl | None = None


class FactCheckFeedbackRecord(FactCheckFeedbackCreate):
    id: str
    fact_check_id: str


class ClaimSelection(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> "ClaimSelection":
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("Choose each claim only once.")
        return self


class FactCheckJob(BaseModel):
    id: str
    analysis_id: str
    status: FactCheckStatus
    stage: str
    progress: Annotated[int, Field(ge=0, le=100)]
    candidates: list[ClaimCandidate] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    result: FactCheckResult | None = None
    error: str | None = None
