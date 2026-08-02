<script lang="ts">
  import EvidenceSourceCard from "./EvidenceSourceCard.svelte";
  import FactCheckFeedback from "./FactCheckFeedback.svelte";
  import {
    languageNames,
    type ClaimCheckResult,
    type ClaimEvidenceStatus,
    type EvidenceItem,
    type FactCheckJob,
    type TraceEvidenceState
  } from "./types";

  export let job: FactCheckJob;

  const evidenceStateCopy = {
    corroborated: "Corroborated across independent reporting",
    conflicting: "Sources differ on a material detail",
    unresolved: "Still unresolved"
  } satisfies Record<TraceEvidenceState, string>;

  const fallbackState = {
    supported: "corroborated",
    disputed: "conflicting",
    mixed: "conflicting",
    insufficient: "unresolved"
  } satisfies Record<ClaimEvidenceStatus, TraceEvidenceState>;

  const relationCopy = {
    supports: "Agrees with the claim",
    disputes: "Challenges the claim",
    context: "Adds important context",
    irrelevant: "Not used"
  } as const;

  function citedEvidence(result: ClaimCheckResult): EvidenceItem[] {
    const cited = new Set([
      ...result.assessment.support_evidence_ids,
      ...result.assessment.challenge_evidence_ids,
      ...result.assessment.context_evidence_ids
    ]);
    return result.evidence.filter((item) => cited.has(item.id));
  }

  function unusedEvidence(result: ClaimCheckResult): EvidenceItem[] {
    const cited = new Set(citedEvidence(result).map((item) => item.id));
    return result.evidence.filter((item) => !cited.has(item.id));
  }

  function traceState(result: ClaimCheckResult): TraceEvidenceState {
    return result.trace?.evidence_state ?? fallbackState[result.assessment.status];
  }

  function lineageCount(result: ClaimCheckResult, evidence: EvidenceItem[]): number {
    return result.trace?.independent_lineages ?? new Set(evidence.map((item) => item.cluster_id)).size;
  }

  function basisCopy(result: ClaimCheckResult, evidence: EvidenceItem[]): string {
    const articles = result.trace?.article_count ?? new Set(evidence.map((item) => item.url)).size;
    const lineages = lineageCount(result, evidence);
    const languages =
      result.trace?.languages ?? [...new Set(evidence.map((item) => item.language))];
    const languageList = languages.map((language) => languageNames[language]).join(", ");
    return `${articles} ${articles === 1 ? "article" : "articles"} · ${lineages} independent ${
      lineages === 1 ? "lineage" : "lineages"
    }${languageList ? ` · ${languageList}` : ""}`;
  }

  function cleanExplanation(value: string, evidence: EvidenceItem[]): string {
    return evidence
      .reduce((cleaned, item) => cleaned.replaceAll(`[${item.id}]`, ""), value)
      .replace(/\s+/g, " ")
      .trim();
  }

  function summaryHeading(state: TraceEvidenceState): string {
    if (state === "corroborated") return "What the sources agree on";
    if (state === "conflicting") return "Where the evidence differs";
    return "What we could establish";
  }

  function differenceCopy(evidence: EvidenceItem[]): string {
    const aligned = evidence.filter(
      (item) => item.alignment_state === "aligned" || item.alignment_state === "partial"
    );
    const uncertain = evidence.some((item) => item.alignment_state === "uncertain");
    if (!aligned.length) {
      return "No cross-language passage was aligned reliably enough to compare wording.";
    }
    if (uncertain) {
      return "No material difference was found in the aligned passages. Other passages could not be matched exactly.";
    }
    return "The aligned passages preserved the claim’s material meaning.";
  }

  function lineageNote(result: ClaimCheckResult, evidence: EvidenceItem[]): string | null {
    const articles = result.trace?.article_count ?? new Set(evidence.map((item) => item.url)).size;
    const lineages = lineageCount(result, evidence);
    if (articles <= lineages) return null;
    return `${articles} articles count as ${lineages} independent ${
      lineages === 1 ? "lineage" : "lineages"
    } because credited or repeated reporting was grouped together.`;
  }

  function checkedDate(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? value
      : new Intl.DateTimeFormat(undefined, {
          dateStyle: "long",
          timeStyle: "short"
        }).format(parsed);
  }

  $: result = job.result;
</script>

{#if result}
  <div class="fact-check-results">
    <header class="fact-check-heading">
      <div>
        <p class="progress-kicker">Claim Trace</p>
        <h1>How this claim travels across reporting</h1>
        <p>
          Checked {checkedDate(result.checked_at)}. This compares available sources; it is
          not a permanent truth rating.
        </p>
      </div>
    </header>

    <div class="checked-claims">
      {#each result.claims as claimResult}
        {@const cited = citedEvidence(claimResult)}
        {@const unused = unusedEvidence(claimResult)}
        {@const state = traceState(claimResult)}
        {@const deltas = claimResult.trace?.meaning_deltas ?? []}
        {@const groupedLineageNote = lineageNote(claimResult, cited)}

        <article class="checked-claim">
          <header class="claim-assessment">
            <p class="claim-position">
              {claimResult.claim.claim_type === "attributed"
                ? "Reported statement"
                : "Factual claim"}
            </p>
            <h2 lang={claimResult.claim.source_language ?? undefined}>
              {claimResult.claim.standalone_claim}
            </h2>
            <details class="source-wording">
              <summary>See the article’s exact wording</summary>
              <blockquote lang={claimResult.claim.source_language ?? undefined}>
                “{claimResult.claim.source_quote}”
              </blockquote>
            </details>
            <strong class={`assessment-status ${state}`}>{evidenceStateCopy[state]}</strong>
            <p class="assessment-basis">{basisCopy(claimResult, cited)}</p>
          </header>

          <section class="trace-section shared-facts" aria-labelledby={`shared-${claimResult.claim.id}`}>
            <h3 id={`shared-${claimResult.claim.id}`}>{summaryHeading(state)}</h3>
            <p>{cleanExplanation(claimResult.assessment.explanation, cited)}</p>
            <FactCheckFeedback
              factCheckId={job.id}
              targetType="status"
              targetId={claimResult.claim.id}
              question="Does this summary follow from the cited evidence?"
            />
          </section>

          <section class="trace-section" aria-labelledby={`changed-${claimResult.claim.id}`}>
            <h3 id={`changed-${claimResult.claim.id}`}>What changed across languages</h3>
            {#if deltas.length}
              <ul class="meaning-deltas">
                {#each deltas as delta}
                  <li>
                    <strong>{delta.type.replace("-", " ")}</strong>
                    <span>{delta.description}</span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p>{differenceCopy(cited)}</p>
            {/if}
          </section>

          <section class="trace-section" aria-labelledby={`trail-${claimResult.claim.id}`}>
            <h3 id={`trail-${claimResult.claim.id}`}>Source trail</h3>
            {#if cited.length}
              <ol class="source-trail">
                {#each cited as evidence}
                  <li>
                    <a href={`#${evidence.id}`}>{evidence.publisher}</a>
                    <span>{languageNames[evidence.language]}</span>
                    <span>{relationCopy[evidence.stance ?? "irrelevant"]}</span>
                    {#if evidence.credited_origin}
                      <span>Credits {evidence.credited_origin}</span>
                    {/if}
                  </li>
                {/each}
              </ol>
            {:else}
              <p>No readable source could be tied to this claim.</p>
            {/if}
            {#if groupedLineageNote}
              <p class="lineage-note">{groupedLineageNote}</p>
            {/if}
          </section>

          {#if claimResult.assessment.limitations.length}
            <aside class:unresolved={state === "unresolved"} class="assessment-limitations">
              <h3>{state === "unresolved" ? "Still unresolved" : "Limits of this trace"}</h3>
              <ul>
                {#each claimResult.assessment.limitations as limitation}
                  <li>{limitation}</li>
                {/each}
              </ul>
            </aside>
          {/if}

          {#if cited.length}
            <section class="evidence-section" aria-labelledby={`evidence-${claimResult.claim.id}`}>
              <h3 id={`evidence-${claimResult.claim.id}`}>Evidence excerpts</h3>
              <p>Open any source to read the reporting around the quoted passage.</p>
              <div class="evidence-list">
                {#each cited as evidence}
                  <EvidenceSourceCard {evidence} factCheckId={job.id} />
                {/each}
              </div>
            </section>
          {/if}

          {#if unused.length}
            <details class="unused-evidence">
              <summary>{unused.length} other {unused.length === 1 ? "passage" : "passages"} reviewed</summary>
              <p>These passages did not determine the trace.</p>
              <div class="evidence-list">
                {#each unused as evidence}
                  <EvidenceSourceCard {evidence} factCheckId={job.id} />
                {/each}
              </div>
            </details>
          {/if}

          {#if claimResult.retrieval_failures.length}
            <details class="source-failures">
              <summary>Some sources could not be checked</summary>
              <ul>
                {#each claimResult.retrieval_failures as failure}
                  <li>{failure.reason}</li>
                {/each}
              </ul>
            </details>
          {/if}

          {#if claimResult.queries.length}
            <details class="search-scope">
              <summary>See what was searched</summary>
              <p>Search phrases are shown for transparency. Coverage may still be incomplete.</p>
              <dl>
                {#each claimResult.queries as query}
                  <div>
                    <dt>{languageNames[query.language]}</dt>
                    <dd>{query.exact_query}</dd>
                    <dd>{query.context_query}</dd>
                    {#if query.challenge_query}<dd>{query.challenge_query}</dd>{/if}
                  </div>
                {/each}
              </dl>
            </details>
          {/if}
        </article>
      {/each}
    </div>
  </div>
{/if}
