export const languages = ["en", "vi", "ko"] as const;
export type Language = (typeof languages)[number];

export const languageNames = {
  en: "English",
  vi: "Vietnamese",
  ko: "Korean"
} satisfies Record<Language, string>;

export type AnalysisStatus =
  | "queued"
  | "extracting"
  | "translating"
  | "analyzing"
  | "complete"
  | "failed";

export type FlagKind = "meaning-risk" | "cultural-note" | "uncertain";
export type FeedbackVerdict = "helpful" | "incorrect" | "unsure";
export type ReviewerRole = "author" | "independent" | "unspecified";
export type FeedbackSaveState = "saving" | "saved" | "error";

export interface AmbiguityFlag {
  id: string;
  target_language: Language;
  kind: FlagKind;
  category: string;
  confidence: "high" | "medium" | null;
  source_quote: string;
  translation_quote: string | null;
  explanation: string;
  alternative: string | null;
  signals: string[];
}

export interface TargetTranslation {
  language: Language;
  text: string;
  shadow_text: string | null;
  similarity: number | null;
  back_translation_similarity: number | null;
  flags: AmbiguityFlag[];
}

export interface SegmentResult {
  id: string;
  paragraph_index: number;
  sentence_index: number;
  source_text: string;
  translations: TargetTranslation[];
}

export interface AnalysisResult {
  source_language: Language;
  source_title: string | null;
  source_url: string | null;
  segments: SegmentResult[];
}

export interface AnalysisJob {
  id: string;
  status: AnalysisStatus;
  stage: string;
  progress: number;
  result: AnalysisResult | null;
  error: string | null;
}

export type FactCheckStatus =
  | "extracting_claims"
  | "awaiting_selection"
  | "retrieving"
  | "ranking"
  | "aligning"
  | "synthesizing"
  | "complete"
  | "failed";

export type ClaimType = "fact" | "attributed" | "unsuitable";
export type ClaimModality = "asserted" | "uncertain" | "future" | "denied";
export type LegalState = "allegation" | "investigation" | "filing" | "ruling" | "finding";

export interface ClaimFacets {
  attribution: string | null;
  modality: ClaimModality;
  legal_state: LegalState | null;
}

export interface ClaimCandidate {
  id: string;
  source_quote: string;
  segment_ids: string[];
  standalone_claim: string;
  claim_type: ClaimType;
  entities: string[];
  dates: string[];
  numbers: string[];
  source_language?: Language | null;
  facets?: ClaimFacets;
  reason: string;
}

export interface SearchQuery {
  language: Language;
  exact_query: string;
  context_query: string;
  challenge_query?: string | null;
}

export type EvidenceStance = "supports" | "disputes" | "context" | "irrelevant";
export type EvidenceSourceKind =
  | "primary"
  | "professional-fact-check"
  | "direct-reporting"
  | "secondary-commentary";
export type ClaimEvidenceStatus = "supported" | "disputed" | "mixed" | "insufficient";
export type FactCheckFeedbackTarget = "evidence" | "status";
export type AlignmentState = "aligned" | "partial" | "not-aligned" | "uncertain";
export type MeaningDeltaType =
  | "certainty"
  | "scope"
  | "attribution"
  | "number"
  | "date"
  | "legal-state"
  | "context";
export type TraceEvidenceState = "corroborated" | "conflicting" | "unresolved";

export interface MeaningDelta {
  type: MeaningDeltaType;
  description: string;
}

export interface EvidenceItem {
  id: string;
  url: string;
  title: string | null;
  publisher: string;
  publisher_key: string | null;
  language: Language;
  excerpt: string;
  source_type: EvidenceSourceKind;
  rating: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  content_hash: string;
  cluster_id: string;
  relevance: number;
  stance: EvidenceStance | null;
  stance_reason: string | null;
  direct: boolean | null;
  mismatch: string | null;
  aligned_quote?: string | null;
  alignment_state?: AlignmentState;
  meaning_deltas?: MeaningDelta[];
  credited_origin?: string | null;
}

export interface RetrievalFailure {
  url: string | null;
  reason: string;
}

export interface ClaimAssessment {
  claim_id: string;
  status: ClaimEvidenceStatus;
  explanation: string;
  support_evidence_ids: string[];
  challenge_evidence_ids: string[];
  context_evidence_ids: string[];
  limitations: string[];
}

export interface ClaimCheckResult {
  claim: ClaimCandidate;
  queries: SearchQuery[];
  evidence: EvidenceItem[];
  assessment: ClaimAssessment;
  trace?: {
    evidence_state: TraceEvidenceState;
    article_count: number;
    independent_lineages: number;
    languages: Language[];
    meaning_deltas: MeaningDelta[];
  } | null;
  retrieval_failures: RetrievalFailure[];
  error: string | null;
}

export interface FactCheckResult {
  claims: ClaimCheckResult[];
  checked_at: string;
}

export interface FactCheckJob {
  id: string;
  analysis_id: string;
  status: FactCheckStatus;
  stage: string;
  progress: number;
  candidates: ClaimCandidate[];
  selected_candidate_ids: string[];
  result: FactCheckResult | null;
  error: string | null;
}

export type InputMode = "text" | "url";

export interface AnalysisDraft {
  mode: InputMode;
  sourceLanguage: Language;
  targetLanguage: Language;
  text: string;
  url: string;
}

export interface AnalysisInput {
  mode: InputMode;
  sourceLanguage: Language;
  targetLanguage: Language;
  value: string;
}

export type ViewState =
  | { kind: "input" }
  | { kind: "running"; job: AnalysisJob }
  | { kind: "results"; job: AnalysisJob & { result: AnalysisResult } }
  | { kind: "fact-check"; job: FactCheckJob };
