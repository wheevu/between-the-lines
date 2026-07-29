<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { AmbiguityFlag, FeedbackVerdict } from "./types";

  export let flag: AmbiguityFlag;
  export let feedback: FeedbackVerdict | null = null;
  export let shadowText: string | null = null;

  const dispatch = createEventDispatcher<{ feedback: FeedbackVerdict }>();

  const labels = {
    "meaning-risk": "Possible meaning change",
    "cultural-note": "Language note",
    uncertain: "Needs a closer read"
  } as const;
</script>

<article class={`flag-detail ${flag.kind}`}>
  <header>
    <span class="flag-kind">{labels[flag.kind]}</span>
    <span class="flag-category">{flag.category.replaceAll("-", " ")}</span>
    {#if flag.confidence}<span class="confidence">{flag.confidence} confidence</span>{/if}
  </header>
  <p>{flag.explanation}</p>
  {#if flag.alternative}
    <p class="alternative"><strong>Another reading:</strong> {flag.alternative}</p>
  {/if}
  <dl>
    <div>
      <dt>Original</dt>
      <dd>{flag.source_quote}</dd>
    </div>
    {#if flag.translation_quote}
      <div>
        <dt>Translation</dt>
        <dd>{flag.translation_quote}</dd>
      </div>
    {/if}
  </dl>

  {#if shadowText}
    <details class="local-check">
      <summary>Offline experiment comparison</summary>
      <p>{shadowText}</p>
    </details>
  {/if}

  <div class="feedback" aria-label="Was this finding useful?">
    <span>Did this help?</span>
    {#each ["helpful", "incorrect", "unsure"] as verdict}
      <button
        class:chosen={feedback === verdict}
        type="button"
        aria-pressed={feedback === verdict}
        on:click={() => dispatch("feedback", verdict as FeedbackVerdict)}
      >
        {verdict === "helpful" ? "Yes" : verdict === "incorrect" ? "No" : "Unsure"}
      </button>
    {/each}
  </div>
</article>
