"""Pydantic models and bounded response types for Between the Lines."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Language(StrEnum):
    ENGLISH = "en"
    VIETNAMESE = "vi"
    KOREAN = "ko"


LanguageOrAuto = Literal["en", "vi", "ko", "auto"]


class DriftCategory(StrEnum):
    NUMBER = "number"
    DATE = "date"
    NEGATION = "negation"
    MODALITY_SHIFT = "modality_shift"
    LEGAL_STATE_SHIFT = "legal_state_shift"
    ATTRIBUTION_LOSS = "attribution_loss"
    UNANCHORED_QUOTE = "unanchored_quote"


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


class Segment(BaseModel):
    id: str
    paragraph_index: int
    sentence_index: int
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    text: str


class ExtractedDocument(BaseModel):
    url: str
    canonical_url: str
    title: str | None = None
    published_at_unverified: str | None = None
    publisher: str
    text: str


class TranslationPairInput(BaseModel):
    pair_id: str | None = None
    source_text: str = Field(min_length=1)
    translation_text: str = Field(min_length=1)
    source_language: LanguageOrAuto = "auto"
    target_language: LanguageOrAuto = "auto"
    source_quote: str | None = None
    translation_quote: str | None = None


class DriftFlag(BaseModel):
    category: DriftCategory
    confidence: Literal["high", "medium"]
    source_quote: str | None = None
    translation_quote: str | None = None
    explanation: str
    details: dict[str, Any] = Field(default_factory=dict)


class PairAuditResult(BaseModel):
    pair_id: str
    source_language: Language
    target_language: Language
    status: Literal["clean", "drift_detected"]
    flags: list[DriftFlag] = Field(default_factory=list)
    source_numbers: list[str] = Field(default_factory=list)
    translation_numbers: list[str] = Field(default_factory=list)
    source_modality: ClaimModality
    translation_modality: ClaimModality
    source_legal_state: LegalState | None = None
    translation_legal_state: LegalState | None = None


class TranslationAuditResult(BaseModel):
    status: Literal["clean", "drift_detected"]
    pair_count: int = Field(ge=0)
    flagged_count: int = Field(ge=0)
    pairs: list[PairAuditResult] = Field(default_factory=list)
    truncated: bool = False
    dropped_fields: list[str] = Field(default_factory=list)


class ClaimInput(BaseModel):
    id: str | None = None
    source_quote: str = Field(min_length=1)
    standalone_claim: str = Field(min_length=1)
    segment_ids: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    attribution: str | None = None


class SearchQueryInput(BaseModel):
    language: Language
    exact_query: str = Field(min_length=1)
    context_query: str = ""
    challenge_query: str | None = None


class ClaimFacetReport(BaseModel):
    language: Language
    modality: ClaimModality
    legal_state: LegalState | None = None
    has_negation: bool
    has_attribution: bool
    numbers: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)


class ClaimGroundingCheck(BaseModel):
    id: str
    grounded: bool
    reasons: list[str] = Field(default_factory=list)
    facets: ClaimFacetReport
    grounded_entities: list[str] = Field(default_factory=list)
    grounded_dates: list[str] = Field(default_factory=list)
    grounded_numbers: list[str] = Field(default_factory=list)
    grounded_attribution: str | None = None


class QueryAnchorCheck(BaseModel):
    language: Language
    passed: bool
    missing_anchors: list[str] = Field(default_factory=list)


class AnalyzeClaimsResult(BaseModel):
    language: Language
    segment_count: int = Field(ge=0)
    segments: list[Segment] = Field(default_factory=list)
    text_facets: ClaimFacetReport
    claim_checks: list[ClaimGroundingCheck] = Field(default_factory=list)
    query_checks: list[QueryAnchorCheck] = Field(default_factory=list)
    truncated: bool = False
    dropped_fields: list[str] = Field(default_factory=list)


class EditionDiffCategory(StrEnum):
    NUMBER = "number"
    DATE = "date"
    NEGATION = "negation"
    NAME = "name"
    MODALITY = "modality"
    LEGAL_STATE = "legal_state"
    TERMINOLOGY = "terminology"


class EditionSignals(BaseModel):
    numbers: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    negations: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    modality: ClaimModality = ClaimModality.ASSERTED
    legal_state: LegalState | None = None
    terminology: list[str] = Field(default_factory=list)


class EditionDiffChange(BaseModel):
    category: EditionDiffCategory
    removed: list[str] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)


class EditionDiffResult(BaseModel):
    changed: bool
    before_language: Language
    after_language: Language
    before_sha256: str
    after_sha256: str
    changes: list[EditionDiffChange] = Field(default_factory=list)
    truncated: bool = False
    dropped_fields: list[str] = Field(default_factory=list)


class OriginInputItem(BaseModel):
    id: str | None = None
    url: str | None = None
    publisher: str = ""
    credited_origin: str | None = None
    language: LanguageOrAuto = "auto"
    excerpt: str | None = None
    title: str | None = None


class OriginCluster(BaseModel):
    lineage_id: str
    canonical_origin: str
    basis: Literal["exact", "alias", "acronym", "near_duplicate", "embedding", "url"]
    independence_hint: Literal["resolved-shared", "resolved-independent"]
    member_ids: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    origins_seen: list[str] = Field(default_factory=list)


class OriginClusterResult(BaseModel):
    source_count: int = Field(ge=0)
    independent_lineage_count: int = Field(ge=0)
    syndication_collapsed: int = Field(ge=0)
    embeddings_used: bool = False
    clusters: list[OriginCluster] = Field(default_factory=list)
    research_ledger_origins: list[dict[str, str]] | None = None
    truncated: bool = False
    dropped_fields: list[str] = Field(default_factory=list)


class DocumentInput(BaseModel):
    url: str | None = None
    title: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    text: str = Field(min_length=1)
    language: LanguageOrAuto = "auto"


class RankedExcerpt(BaseModel):
    excerpt_id: str
    url: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    publisher: str
    language: Language
    published_at_unverified: str | None = None
    excerpt: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    content_hash: str
    cluster_id: str
    relevance: float
    scoring_method: Literal["e5", "lexical"]


class RetrievalFailure(BaseModel):
    url: str | None = None
    reason: str


class ExtractRankResult(BaseModel):
    claim: str
    claim_language: Language
    embeddings_used: bool
    documents_processed: int = Field(ge=0)
    excerpts: list[RankedExcerpt] = Field(default_factory=list)
    failures: list[RetrievalFailure] = Field(default_factory=list)
    research_ledger_packet: dict[str, Any] | None = None
    truncated: bool = False
    dropped_fields: list[str] = Field(default_factory=list)
