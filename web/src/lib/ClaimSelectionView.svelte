<script lang="ts">
  import FactCheckProgress from "./FactCheckProgress.svelte";
  import FactCheckResults from "./FactCheckResults.svelte";
  import type { ClaimCandidate, FactCheckJob } from "./types";

  export let job: FactCheckJob;
  export let onSelect: (candidateIds: string[]) => Promise<void>;
  export let onReset: () => void;

  let selectedId = job.selected_candidate_ids[0] ?? null;
  let saveState: "idle" | "saving" | "saved" | "error" = job.selected_candidate_ids.length
    ? "saved"
    : "idle";
  let errorMessage = "";

  $: hasPartialResults = Boolean(job.result?.claims.length);

  function isSuitable(candidate: ClaimCandidate): boolean {
    return candidate.claim_type !== "unsuitable";
  }

  function choose(candidateId: string) {
    selectedId = candidateId;
    saveState = "idle";
  }

  async function submit() {
    if (!selectedId) return;
    saveState = "saving";
    errorMessage = "";
    try {
      await onSelect([selectedId]);
      saveState = "saved";
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : "Couldn't save this claim.";
      saveState = "error";
    }
  }
</script>

<section class="claim-shell">
  <button class="back-action" type="button" on:click={onReset}>← New article</button>

  {#if job.status === "extracting_claims"}
    <div class="claim-progress" aria-live="polite" aria-busy="true">
      <p class="progress-kicker">Claim Trace</p>
      <h1>{job.stage}</h1>
      <p>Looking for specific statements that can be compared across independent reporting.</p>
    </div>
  {:else if job.status === "complete" || (job.status === "failed" && hasPartialResults)}
    {#if job.status === "failed"}
      <div class="partial-result-warning" role="alert">
        <strong>The check stopped before every claim finished.</strong>
        <p>{job.error ?? "The completed source comparisons are still available below."}</p>
      </div>
    {/if}
    <FactCheckResults {job} />
  {:else if job.status === "retrieving" || job.status === "ranking" || job.status === "aligning" || job.status === "synthesizing"}
    <FactCheckProgress {job} />
  {:else if job.status === "failed"}
    <div class="claim-progress" role="alert">
      <p class="progress-kicker">Claim Trace</p>
      <h1>The check couldn’t finish</h1>
      <p>{job.error ?? "Try this article again later."}</p>
    </div>
  {:else}
    <header class="claim-heading">
      <div>
        <p class="progress-kicker">Claim Trace</p>
        <h1>Which claim should we follow?</h1>
        <p>Choose one specific claim to compare across English, Vietnamese, and Korean reporting.</p>
      </div>
      <p class="selection-count" aria-live="polite">{selectedId ? "1 selected" : "Nothing selected"}</p>
    </header>

    <div class="claim-list">
      {#each job.candidates as candidate}
        <article
          class:claim-unsuitable={!isSuitable(candidate)}
          class="claim-card"
          id={`claim-${candidate.id}`}
        >
          <label>
            <input
              type="radio"
              name="claim-to-trace"
              checked={selectedId === candidate.id}
              disabled={!isSuitable(candidate)}
              aria-describedby={`claim-reason-${candidate.id}`}
              on:change={() => choose(candidate.id)}
            />
            <span>
              <span class="claim-type">
                {candidate.claim_type === "attributed"
                  ? "Reported statement"
                  : candidate.claim_type === "fact"
                    ? "Factual claim"
                    : "Not suitable"}
              </span>
              <strong lang={candidate.source_language ?? undefined}>{candidate.standalone_claim}</strong>
            </span>
          </label>
          <blockquote lang={candidate.source_language ?? undefined}>“{candidate.source_quote}”</blockquote>
          <p id={`claim-reason-${candidate.id}`}>{candidate.reason}</p>
          {#if candidate.entities.length || candidate.dates.length || candidate.numbers.length}
            <ul class="claim-signals" aria-label="Details preserved from the quote">
              {#each [...candidate.entities, ...candidate.dates, ...candidate.numbers] as signal}
                <li>{signal}</li>
              {/each}
            </ul>
          {/if}
        </article>
      {/each}
    </div>

    <footer class="claim-actions">
      <button
        class="primary-action"
        type="button"
        disabled={!selectedId || saveState === "saving"}
        on:click={submit}
      >
        {saveState === "saving" ? "Starting trace…" : selectedId ? "Trace this claim" : "Choose a claim"}
      </button>
      <p>
        {job.selected_candidate_ids.length
          ? "The claim is saved. Evidence search is waiting for translation review."
          : "We’ll trace the claim through related reporting and show where the wording changes."}
      </p>
      {#if saveState === "saved"}
        <span class="save-status" role="status">Selection saved.</span>
      {:else if saveState === "error"}
        <span class="save-error" role="alert">{errorMessage}</span>
      {/if}
    </footer>
  {/if}
</section>
