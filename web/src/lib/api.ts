import type {
  AnalysisInput,
  AnalysisJob,
  FactCheckJob,
  FactCheckFeedbackTarget,
  FeedbackVerdict,
  ReviewerRole,
} from "./types";

interface ErrorResponse {
  detail?: string;
}

export async function createAnalysis(
  input: AnalysisInput,
  signal?: AbortSignal
): Promise<AnalysisJob> {
  const response = await fetch("/api/analyses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      source_language: input.sourceLanguage,
      target_language: input.targetLanguage,
      ...(input.mode === "text" ? { text: input.value } : { url: input.value })
    }),
    signal
  });
  return readResponse<AnalysisJob>(response);
}

export async function getAnalysis(id: string, signal?: AbortSignal): Promise<AnalysisJob> {
  const response = await fetch(`/api/analyses/${id}`, { signal });
  return readResponse<AnalysisJob>(response);
}

export async function getFactCheck(
  id: string,
  signal?: AbortSignal
): Promise<FactCheckJob> {
  const response = await fetch(`/api/fact-checks/${id}`, { signal });
  return readResponse<FactCheckJob>(response);
}

export async function createFactCheck(
  analysisId: string,
  signal?: AbortSignal
): Promise<FactCheckJob> {
  const response = await fetch(`/api/analyses/${analysisId}/fact-checks`, {
    method: "POST",
    signal
  });
  return readResponse<FactCheckJob>(response);
}

export async function selectFactCheckClaims(
  id: string,
  candidateIds: string[],
  signal?: AbortSignal
): Promise<FactCheckJob> {
  const response = await fetch(`/api/fact-checks/${id}/selection`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds }),
    signal
  });
  return readResponse<FactCheckJob>(response);
}

export async function sendFactCheckFeedback(
  factCheckId: string,
  targetType: FactCheckFeedbackTarget,
  targetId: string,
  verdict: FeedbackVerdict,
  correction?: string,
  betterSourceUrl?: string,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`/api/fact-checks/${factCheckId}/feedback`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      target_type: targetType,
      target_id: targetId,
      verdict,
      ...(correction ? { correction } : {}),
      ...(betterSourceUrl ? { better_source_url: betterSourceUrl } : {})
    }),
    signal
  });
  await readResponse(response);
}

export async function sendFeedback(
  analysisId: string,
  flagId: string,
  verdict: FeedbackVerdict,
  correction?: string,
  reviewerRole: ReviewerRole = "unspecified",
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`/api/analyses/${analysisId}/feedback`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      flag_id: flagId,
      verdict,
      ...(correction ? { correction } : {}),
      reviewer_role: reviewerRole
    }),
    signal
  });
  await readResponse(response);
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "Couldn't reach the translation service. Try again.";
    try {
      const body = (await response.json()) as ErrorResponse;
      if (body.detail) message = body.detail;
    } catch {
      // Keep the plain fallback when the server did not return JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}
