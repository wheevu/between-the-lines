<script lang="ts">
  import { sendFactCheckFeedback } from "./api";
  import type {
    FactCheckFeedbackTarget,
    FeedbackSaveState,
    FeedbackVerdict
  } from "./types";

  export let factCheckId: string;
  export let targetType: FactCheckFeedbackTarget;
  export let targetId: string;
  export let question: string;

  let verdict: FeedbackVerdict | null = null;
  let correction = "";
  let betterSourceUrl = "";
  let saveState: FeedbackSaveState | "idle" = "idle";

  async function choose(nextVerdict: FeedbackVerdict) {
    verdict = nextVerdict;
    await save();
  }

  async function save() {
    if (!verdict) return;
    saveState = "saving";
    try {
      await sendFactCheckFeedback(
        factCheckId,
        targetType,
        targetId,
        verdict,
        correction.trim() || undefined,
        betterSourceUrl.trim() || undefined
      );
      saveState = "saved";
    } catch {
      saveState = "error";
    }
  }
</script>

<div class="fact-feedback">
  <p>{question}</p>
  <div class="fact-feedback-actions" aria-label={question}>
    <button
      type="button"
      class:chosen={verdict === "helpful"}
      aria-pressed={verdict === "helpful"}
      on:click={() => choose("helpful")}
    >Yes</button>
    <button
      type="button"
      class:chosen={verdict === "incorrect"}
      aria-pressed={verdict === "incorrect"}
      on:click={() => choose("incorrect")}
    >No</button>
    <button
      type="button"
      class:chosen={verdict === "unsure"}
      aria-pressed={verdict === "unsure"}
      on:click={() => choose("unsure")}
    >Unsure</button>
  </div>

  {#if verdict === "incorrect" || verdict === "unsure"}
    <div class="fact-feedback-detail">
      <label for={`correction-${targetId}`}>What should change? <span>Optional</span></label>
      <textarea
        id={`correction-${targetId}`}
        rows="2"
        maxlength="1000"
        bind:value={correction}
      ></textarea>
      <label for={`source-${targetId}`}>Better source <span>Optional URL</span></label>
      <input id={`source-${targetId}`} type="url" bind:value={betterSourceUrl} />
      <button class="secondary-action" type="button" disabled={saveState === "saving"} on:click={save}>
        {saveState === "saving" ? "Saving…" : "Save note"}
      </button>
    </div>
  {/if}

  {#if saveState === "saved"}
    <span class="save-status" role="status">Feedback saved.</span>
  {:else if saveState === "error"}
    <span class="save-error" role="alert">Couldn’t save feedback. Try again.</span>
  {/if}
</div>
