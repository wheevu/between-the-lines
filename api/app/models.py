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
    fallback_url: HttpUrl | None = None

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


class LedgerStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    SUPPORTED = "supported"
    DISPUTED = "disputed"
    UNCLEAR = "unclear"
    CHANGED = "changed"
    SUPERSEDED = "superseded"


class SourceSnapshotStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    CHANGED = "changed"


class EvidenceLinkRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class TranslationCheckStatus(StrEnum):
    UNCHECKED = "unchecked"
    PRESERVED = "preserved"
    CHANGED = "changed"
    UNCLEAR = "unclear"


class RevisionEventType(StrEnum):
    CREATED = "created"
    SOURCE_CAPTURED = "source-captured"
    CLAIM_REVIEWED = "claim-reviewed"
    EDITION_DIFFED = "edition-diffed"
    SUPERSEDED = "superseded"


class EditionDiffCategory(StrEnum):
    NUMBER = "number"
    DATE = "date"
    NEGATION = "negation"
    NAME = "name"
    TERMINOLOGY = "terminology"


class EditionSignals(BaseModel):
    numbers: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    negations: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)


class EditionDiffChange(BaseModel):
    category: EditionDiffCategory
    removed: list[str] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)


class SourceSnapshotCreate(BaseModel):
    url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=300)
    excerpt: str = Field(default="", max_length=2_000)
    source_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"(?i)^[0-9a-f]{64}$",
    )
    start_offset: int = Field(default=0, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    status: SourceSnapshotStatus = SourceSnapshotStatus.AVAILABLE


class TranslationCheckCreate(BaseModel):
    target_language: Language
    translation_text: str = Field(min_length=1, max_length=2_000)
    status: TranslationCheckStatus = TranslationCheckStatus.UNCHECKED
    source_claim_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"(?i)^[0-9a-f]{64}$",
    )
    notes: str | None = Field(default=None, max_length=500)


class ClaimLedgerEntryCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    segment_id: str | None = Field(default=None, max_length=200)
    translation_checks: list[TranslationCheckCreate] = Field(default_factory=list, max_length=8)


class ArticleEditionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    source_language: Language
    source_url: HttpUrl | None = None
    source_text: str | None = Field(default=None, max_length=100_000)
    source_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"(?i)^[0-9a-f]{64}$",
    )
    source_excerpt: str | None = Field(default=None, max_length=2_000)
    source_excerpt_start: int = Field(default=0, ge=0)
    source_status: SourceSnapshotStatus = SourceSnapshotStatus.AVAILABLE
    source_snapshots: list[SourceSnapshotCreate] = Field(default_factory=list, max_length=20)
    claims: list[ClaimLedgerEntryCreate] = Field(default_factory=list, max_length=200)
    supersedes_edition_id: str | None = Field(default=None, max_length=200)
    revision_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_source_material(self) -> "ArticleEditionCreate":
        if not any(
            (self.source_text, self.source_sha256, self.source_excerpt, self.source_snapshots)
        ):
            raise ValueError(
                "Provide source text, a source hash, an excerpt, or source snapshots."
            )
        return self


class ReviewDecisionCreate(BaseModel):
    edition_id: str = Field(min_length=1, max_length=200)
    claim_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"(?i)^[0-9a-f]{64}$",
    )
    status: LedgerStatus
    reviewer: str = Field(default="local-reviewer", min_length=1, max_length=200)
    rationale: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_review_status(self) -> "ReviewDecisionCreate":
        if self.status is LedgerStatus.UNREVIEWED:
            raise ValueError("A review must choose a substantive ledger status.")
        return self


class SourceSnapshot(BaseModel):
    id: str
    edition_id: str
    url: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    excerpt: str = Field(max_length=2_000)
    excerpt_sha256: str
    source_sha256: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    status: SourceSnapshotStatus
    duplicate_of_id: str | None = None
    captured_at: str


class EvidenceLink(BaseModel):
    id: str
    claim_id: str
    snapshot_id: str
    quote: str = Field(max_length=2_000)
    quote_sha256: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    relation: EvidenceLinkRelation
    created_at: str


class TranslationCheck(BaseModel):
    id: str
    claim_id: str
    edition_id: str
    target_language: Language
    translation_text: str = Field(max_length=2_000)
    translation_sha256: str
    source_claim_hash: str
    status: TranslationCheckStatus
    notes: str | None = None
    created_at: str


class ReviewDecision(BaseModel):
    id: str
    claim_id: str
    edition_id: str
    claim_hash: str
    status: LedgerStatus
    reviewer: str
    rationale: str | None = None
    decided_at: str


class ClaimLedgerEntry(BaseModel):
    id: str
    edition_id: str
    text: str = Field(max_length=2_000)
    claim_hash: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    segment_id: str | None = None
    status: LedgerStatus
    created_at: str
    updated_at: str
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    translation_checks: list[TranslationCheck] = Field(default_factory=list)
    review_decisions: list[ReviewDecision] = Field(default_factory=list)


class RevisionEvent(BaseModel):
    id: str
    article_id: str
    edition_id: str
    event_type: RevisionEventType
    summary: str
    payload_hash: str
    created_at: str


class ArticleEdition(BaseModel):
    id: str
    article_id: str
    version: int = Field(ge=1)
    title: str | None = None
    source_language: Language
    source_url: str | None = None
    source_sha256: str
    source_excerpt: str = Field(max_length=2_000)
    source_excerpt_sha256: str
    source_excerpt_start: int = Field(ge=0)
    source_excerpt_end: int = Field(ge=0)
    source_status: SourceSnapshotStatus
    signals: EditionSignals
    created_at: str
    supersedes_edition_id: str | None = None
    revision_reason: str | None = None
    source_snapshots: list[SourceSnapshot] = Field(default_factory=list)
    claims: list[ClaimLedgerEntry] = Field(default_factory=list)
    revision_events: list[RevisionEvent] = Field(default_factory=list)


class ArticleLedger(BaseModel):
    article_id: str
    latest_edition_id: str | None = None
    editions: list[ArticleEdition] = Field(default_factory=list)


class ArticleExport(BaseModel):
    schema_version: int = 1
    article_id: str
    exported_at: str
    ledger: ArticleLedger


class EditionDiff(BaseModel):
    from_edition_id: str
    against_edition_id: str
    article_id: str
    changed: bool
    from_source_sha256: str
    against_source_sha256: str
    changes: list[EditionDiffChange] = Field(default_factory=list)
