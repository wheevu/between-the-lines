<script lang="ts">
  import { onMount } from "svelte";

  import ArticleForm from "./lib/ArticleForm.svelte";
  import ClaimSelectionView from "./lib/ClaimSelectionView.svelte";
  import ProgressView from "./lib/ProgressView.svelte";
  import ResultsView from "./lib/ResultsView.svelte";
  import {
    createAnalysis,
    createFactCheck,
    getAnalysis,
    getFactCheck,
    selectFactCheckClaims,
    sendFeedback
  } from "./lib/api";
  import type {
    AnalysisDraft,
    AnalysisInput,
    AnalysisJob,
    FeedbackSaveState,
    FeedbackVerdict,
    ReviewerRole,
    ViewState
  } from "./lib/types";

  const emptyDraft: AnalysisDraft = {
    mode: "url",
    sourceLanguage: "en",
    targetLanguage: "vi",
    text: "",
    url: ""
  };

  let state: ViewState = { kind: "input" };
  let draft = { ...emptyDraft };
  let errorMessage = "";
  let feedbackByFlag: Record<string, FeedbackVerdict> = {};
  let feedbackState: Record<string, FeedbackSaveState> = {};
  let activeController: AbortController | null = null;
  let reviewerRole: ReviewerRole = "unspecified";
  let traceStartState: "idle" | "starting" | "error" = "idle";
  let traceStartError = "";
  let showClaimTraceNotice = false;

  $: viewAnnouncement =
    state.kind === "results"
      ? "Translation ready."
      : state.kind === "fact-check" && state.job.status === "awaiting_selection"
        ? "Claim selection ready."
        : state.kind === "fact-check" && state.job.status === "complete"
          ? "Evidence results ready."
          : "";
  $: canUseClaimTrace = reviewerRole !== "unspecified";

  onMount(() => {
    const params = new URL(window.location.href).searchParams;
    const role = params.get("reviewer");
    const isReviewer = role === "author" || role === "independent";
    if (isReviewer) reviewerRole = role;
    const factCheckId = params.get("fact_check");
    if (factCheckId) {
      if (!isReviewer) {
        showClaimTraceNotice = true;
        clearAnalysisUrl();
        return;
      }
      activeController = new AbortController();
      void pollFactCheck(factCheckId, activeController.signal);
      return;
    }

    const analysisId = params.get("analysis");
    if (!analysisId) return;

    activeController = new AbortController();
    state = {
      kind: "running",
      job: {
        id: analysisId,
        status: "queued",
        stage: "Opening this analysis",
        progress: 0,
        result: null,
        error: null
      }
    };
    void poll(analysisId, activeController.signal);
  });

  async function analyze(input: AnalysisInput) {
    activeController?.abort();
    activeController = new AbortController();
    errorMessage = "";
    showClaimTraceNotice = false;
    feedbackByFlag = {};
    feedbackState = {};
    traceStartState = "idle";
    traceStartError = "";
    try {
      const job = await createAnalysis(input, activeController.signal);
      setAnalysisUrl(job.id);
      state = { kind: "running", job };
      await poll(job.id, activeController.signal);
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      showInputError(error);
    }
  }

  async function pollFactCheck(id: string, signal: AbortSignal) {
    try {
      while (!signal.aborted) {
        const job = await getFactCheck(id, signal);
        state = { kind: "fact-check", job };
        if (
          job.status !== "extracting_claims" &&
          job.status !== "retrieving" &&
          job.status !== "ranking" &&
          job.status !== "aligning" &&
          job.status !== "synthesizing"
        ) return;
        await new Promise((resolve) => setTimeout(resolve, 700));
      }
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      showInputError(error);
    }
  }

  async function poll(id: string, signal: AbortSignal) {
    try {
      while (!signal.aborted) {
        const job = await getAnalysis(id, signal);
        if (job.status === "complete" && job.result) {
          state = { kind: "results", job: { ...job, result: job.result } };
          return;
        }
        if (job.status === "failed") {
          showInputError(new Error(job.error ?? "The analysis couldn't finish."));
          return;
        }
        state = { kind: "running", job };
        await new Promise((resolve) => setTimeout(resolve, 900));
      }
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      showInputError(error);
    }
  }

  function showInputError(error: unknown) {
    errorMessage = error instanceof Error ? error.message : "The analysis stopped. Try again.";
    clearAnalysisUrl();
    state = { kind: "input" };
  }

  function returnToDraft() {
    activeController?.abort();
    activeController = null;
    clearAnalysisUrl();
    state = { kind: "input" };
  }

  function newArticle() {
    activeController?.abort();
    activeController = null;
    draft = { ...emptyDraft };
    errorMessage = "";
    showClaimTraceNotice = false;
    feedbackByFlag = {};
    feedbackState = {};
    traceStartState = "idle";
    traceStartError = "";
    clearAnalysisUrl();
    state = { kind: "input" };
  }

  function setAnalysisUrl(id: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("analysis", id);
    window.history.replaceState({}, "", url);
  }

  function clearAnalysisUrl() {
    const url = new URL(window.location.href);
    url.searchParams.delete("analysis");
    url.searchParams.delete("fact_check");
    window.history.replaceState({}, "", url);
  }

  async function startClaimTrace() {
    if (state.kind !== "results" || !canUseClaimTrace) return;
    traceStartState = "starting";
    traceStartError = "";
    try {
      const factCheck = await createFactCheck(state.job.id);
      const url = new URL(window.location.href);
      url.searchParams.set("fact_check", factCheck.id);
      window.history.replaceState({}, "", url);
      state = { kind: "fact-check", job: factCheck };
      traceStartState = "idle";
      activeController?.abort();
      activeController = new AbortController();
      void pollFactCheck(factCheck.id, activeController.signal);
    } catch (error: unknown) {
      traceStartState = "error";
      traceStartError =
        error instanceof Error ? error.message : "Couldn't prepare Claim Trace. Try again.";
    }
  }

  async function saveClaimSelection(candidateIds: string[]) {
    if (state.kind !== "fact-check") return;
    const job = await selectFactCheckClaims(state.job.id, candidateIds);
    state = { kind: "fact-check", job };
    if (
      job.status === "retrieving" ||
      job.status === "ranking" ||
      job.status === "aligning" ||
      job.status === "synthesizing"
    ) {
      activeController?.abort();
      activeController = new AbortController();
      void pollFactCheck(job.id, activeController.signal);
    }
  }

  async function recordFeedback(
    event: CustomEvent<{ flagId: string; verdict: FeedbackVerdict; correction?: string }>
  ) {
    if (state.kind !== "results") return;
    const { flagId, verdict, correction } = event.detail;
    const previous = feedbackByFlag;
    feedbackByFlag = { ...feedbackByFlag, [flagId]: verdict };
    feedbackState = { ...feedbackState, [flagId]: "saving" };
    try {
      await sendFeedback(state.job.id, flagId, verdict, correction, reviewerRole);
      feedbackState = { ...feedbackState, [flagId]: "saved" };
    } catch {
      feedbackByFlag = previous;
      feedbackState = { ...feedbackState, [flagId]: "error" };
    }
  }
</script>

<a class="skip-link" href="#main-content">Skip to content</a>
<p class="sr-only" role="status" aria-live="polite">{viewAnnouncement}</p>

<main id="main-content" tabindex="-1">
  <header class="app-header">
    <button class="wordmark" type="button" on:click={newArticle}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <rect x="2" y="4" width="20" height="3" rx="1.5" fill="currentColor" />
        <rect x="7" y="10.5" width="15" height="3" rx="1.5" fill="currentColor" />
        <rect x="2" y="17" width="20" height="3" rx="1.5" fill="currentColor" />
      </svg>
      Between the Lines
    </button>
    <span>English · Vietnamese · Korean</span>
  </header>

  {#if state.kind === "input"}
    {#if showClaimTraceNotice}
      <div class="form-error" role="alert">
        <div>
          <strong>Claim Trace is still in reviewer testing.</strong>
          <p>Open the reviewer link you were given, or keep using the translation reader.</p>
        </div>
      </div>
    {/if}
    <ArticleForm
      {draft}
      {errorMessage}
      onDraftChange={(nextDraft) => (draft = nextDraft)}
      onAnalyze={analyze}
    />
  {:else if state.kind === "running"}
    <ProgressView job={state.job} onBack={returnToDraft} />
  {:else if state.kind === "results"}
    <ResultsView
      job={state.job}
      {feedbackByFlag}
      {feedbackState}
      {traceStartState}
      {traceStartError}
      showClaimTrace={canUseClaimTrace}
      on:reset={newArticle}
      on:feedback={recordFeedback}
      on:trace={startClaimTrace}
    />
  {:else}
    <ClaimSelectionView
      job={state.job}
      onSelect={saveClaimSelection}
      onReset={newArticle}
    />
  {/if}
</main>
