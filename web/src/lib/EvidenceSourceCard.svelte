<script lang="ts">
  import { languageNames } from "./types";
  import type { EvidenceItem } from "./types";
  import FactCheckFeedback from "./FactCheckFeedback.svelte";

  export let evidence: EvidenceItem;
  export let factCheckId: string;

  const sourceLabels = {
    primary: "Original record",
    "professional-fact-check": "Fact-check",
    "direct-reporting": "News report",
    "secondary-commentary": "Commentary"
  } satisfies Record<EvidenceItem["source_type"], string>;

  function shortDate(value: string | null): string | null {
    if (!value) return null;
    const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
    return Number.isNaN(parsed.getTime())
      ? null
      : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
  }

  $: publishedDate = shortDate(evidence.published_at);
  $: retrievedDate = shortDate(evidence.retrieved_at);
</script>

<article class="evidence-card" id={evidence.id}>
  <header>
    <div>
      <p class="evidence-publisher">{evidence.publisher}</p>
      <h3>{evidence.title ?? "Source excerpt"}</h3>
    </div>
    <a href={evidence.url} target="_blank" rel="noopener noreferrer nofollow">Open source ↗</a>
  </header>

  <ul class="evidence-meta" aria-label="Source details">
    <li>{sourceLabels[evidence.source_type]}</li>
    <li>{languageNames[evidence.language]}</li>
    {#if publishedDate}
      <li>Page date {publishedDate}</li>
    {:else}
      <li class="date-unavailable">No reliable page date</li>
    {/if}
    {#if retrievedDate}<li>Checked {retrievedDate}</li>{/if}
    {#if evidence.direct}<li>Direct evidence</li>{/if}
    {#if evidence.alignment_state === "aligned"}
      <li>Exact claim match</li>
    {:else if evidence.alignment_state === "partial"}
      <li>Partial claim match</li>
    {:else if evidence.alignment_state === "uncertain"}
      <li>Match uncertain</li>
    {:else}
      <li>Different or related claim</li>
    {/if}
  </ul>

  {#if evidence.credited_origin}
    <p class="source-origin"><span>Credited source</span>{evidence.credited_origin}</p>
  {/if}

  {#if evidence.rating}
    <p class="source-rating">
      <span>Publisher’s rating</span>
      {evidence.rating}
    </p>
  {/if}

  <blockquote lang={evidence.language}>{evidence.aligned_quote ?? evidence.excerpt}</blockquote>

  {#if evidence.aligned_quote && evidence.aligned_quote !== evidence.excerpt}
    <details class="evidence-context">
      <summary>See the surrounding excerpt</summary>
      <p lang={evidence.language}>{evidence.excerpt}</p>
    </details>
  {/if}

  {#if evidence.stance_reason}
    <p class="evidence-reason"><strong>Why it matters:</strong> {evidence.stance_reason}</p>
  {/if}
  {#if evidence.mismatch}
    <p class="evidence-mismatch"><strong>Material difference:</strong> {evidence.mismatch}</p>
  {/if}

  <FactCheckFeedback
    {factCheckId}
    targetType="evidence"
    targetId={evidence.id}
    question="Is this evidence relevant?"
  />
</article>
