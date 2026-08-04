<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import FlagDetails from "./FlagDetails.svelte";
  import {
    languageNames,
    type AmbiguityFlag,
    type AnalysisJob,
    type AnalysisResult,
    type FeedbackSaveState,
    type FeedbackVerdict,
    type FlagKind,
    type Language,
    type SegmentResult,
    type TargetTranslation
  } from "./types";

  export let job: AnalysisJob & { result: AnalysisResult };
  export let feedbackByFlag: Record<string, FeedbackVerdict> = {};
  export let feedbackState: Record<string, FeedbackSaveState> = {};
  export let traceStartState: "idle" | "starting" | "error" = "idle";
  export let traceStartError = "";
  export let showClaimTrace = false;

  interface Paragraph {
    index: number;
    segments: SegmentResult[];
  }

  interface Finding {
    flag: AmbiguityFlag;
    segment: SegmentResult;
    translation: TargetTranslation;
  }

  const dispatch = createEventDispatcher<{
    reset: void;
    feedback: { flagId: string; verdict: FeedbackVerdict; correction?: string };
    trace: void;
  }>();

  const overallFeedbackPrefix = "__overall__:";
  const kindPriority: Record<FlagKind, number> = {
    "meaning-risk": 0,
    uncertain: 1,
    "cultural-note": 2
  };

  let activeLanguage: Language | null = null;
  let showOriginal = false;
  let showAllFindings = false;
  let copyState: "idle" | "copied" | "error" = "idle";
  let overallVerdicts: Partial<Record<Language, FeedbackVerdict>> = {};
  let missedIssues: Partial<Record<Language, string>> = {};

  $: targetLanguages = job.result.segments[0]?.translations.map((item) => item.language) ?? [];
  $: if (activeLanguage === null || !targetLanguages.includes(activeLanguage)) {
    activeLanguage = targetLanguages[0] ?? null;
  }
  $: paragraphs = groupParagraphs(job.result.segments);
  $: findings = activeLanguage ? collectFindings(activeLanguage) : [];
  $: visibleFindings = showAllFindings ? findings : findings.slice(0, 4);
  $: activeFeedbackId = activeLanguage ? `${overallFeedbackPrefix}${activeLanguage}` : "";

  function groupParagraphs(segments: SegmentResult[]): Paragraph[] {
    const grouped = new Map<number, SegmentResult[]>();
    for (const segment of segments) {
      const paragraph = grouped.get(segment.paragraph_index) ?? [];
      paragraph.push(segment);
      grouped.set(segment.paragraph_index, paragraph);
    }
    return [...grouped.entries()].map(([index, paragraphSegments]) => ({
      index,
      segments: paragraphSegments
    }));
  }

  function translationFor(
    segment: SegmentResult,
    language: Language | null
  ): TargetTranslation | undefined {
    return segment.translations.find((translation) => translation.language === language);
  }

  function countFindings(language: Language): number {
    return job.result.segments.reduce(
      (count, segment) => count + (translationFor(segment, language)?.flags.length ?? 0),
      0
    );
  }

  function collectFindings(language: Language): Finding[] {
    return job.result.segments
      .flatMap((segment) => {
        const translation = translationFor(segment, language);
        return translation
          ? translation.flags.map((flag) => ({ flag, segment, translation }))
          : [];
      })
      .sort((left, right) => {
        const kindDifference = kindPriority[left.flag.kind] - kindPriority[right.flag.kind];
        if (kindDifference !== 0) return kindDifference;
        if (left.flag.confidence === right.flag.confidence) return 0;
        return left.flag.confidence === "high" ? -1 : 1;
      });
  }

  function selectLanguage(language: Language) {
    activeLanguage = language;
    showAllFindings = false;
    copyState = "idle";
  }

  function articleText(language: Language): string {
    return paragraphs
      .map((paragraph) =>
        paragraph.segments
          .map((segment) => translationFor(segment, language)?.text)
          .filter((text): text is string => Boolean(text))
          .join(" ")
      )
      .join("\n\n");
  }

  async function copyTranslation() {
    if (!activeLanguage) return;
    try {
      await navigator.clipboard.writeText(articleText(activeLanguage));
      copyState = "copied";
    } catch {
      copyState = "error";
    }
  }

  function chooseOverallVerdict(verdict: FeedbackVerdict) {
    if (!activeLanguage) return;
    overallVerdicts = { ...overallVerdicts, [activeLanguage]: verdict };
    if (verdict !== "incorrect") savePassageReview(activeLanguage);
  }

  function savePassageReview(language: Language) {
    const verdict = overallVerdicts[language];
    if (!verdict) return;
    dispatch("feedback", {
      flagId: `${overallFeedbackPrefix}${language}`,
      verdict,
      correction: missedIssues[language]?.trim() || undefined
    });
  }

  function sourceHost(url: string | null): string | null {
    if (!url) return null;
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return null;
    }
  }
</script>

<section class="results-shell">
  <header class="results-header">
    <div>
      <button class="back-action" type="button" on:click={() => dispatch("reset")}>
        ← New article
      </button>
      <h1>{job.result.source_title ?? "Translation ready"}</h1>
      <p>
        {languageNames[job.result.source_language]} original · {paragraphs.length}
        {paragraphs.length === 1 ? "paragraph" : "paragraphs"}
        {#if job.result.source_url && sourceHost(job.result.source_url)}
          · <a href={job.result.source_url} target="_blank" rel="noreferrer">
            {sourceHost(job.result.source_url)} ↗
          </a>
        {/if}
      </p>
    </div>
    <details class="method-note">
      <summary>How this was checked</summary>
      <p>
        Protected facts are checked in every passage. Model notes point out
        translation choices that deserve a closer read.
      </p>
    </details>
  </header>

  {#if showClaimTrace}
    <section class="claim-trace-cta" aria-labelledby="claim-trace-heading">
      <div>
        <h2 id="claim-trace-heading">Trace one claim across languages</h2>
        <p>
          See what English, Vietnamese, and Korean reporting agrees on—and where
          attribution, certainty, dates, or numbers change.
        </p>
      </div>
      <button
        class="primary-action"
        type="button"
        disabled={traceStartState === "starting"}
        on:click={() => dispatch("trace")}
      >
        {traceStartState === "starting" ? "Finding claims…" : "Choose a claim to trace"}
      </button>
      {#if traceStartState === "error"}
        <p class="save-error" role="alert">{traceStartError}</p>
      {/if}
    </section>
  {/if}

  <div class="result-controls">
    <nav class="language-tabs" aria-label="Translation language">
      {#each targetLanguages as language}
        <button
          class:active={activeLanguage === language}
          type="button"
          aria-pressed={activeLanguage === language}
          on:click={() => selectLanguage(language)}
        >
          {languageNames[language]}
          {#if countFindings(language)}
            <span>{countFindings(language)}</span>
          {/if}
        </button>
      {/each}
    </nav>
    <div class="copy-action">
      <button type="button" on:click={copyTranslation}>Copy translation</button>
      {#if copyState === "copied"}
        <span role="status">Copied.</span>
      {:else if copyState === "error"}
        <span class="save-error" role="alert">Couldn’t copy. Select the text instead.</span>
      {/if}
    </div>
  </div>

  <section class="findings-panel" aria-labelledby="findings-heading">
    {#if findings.length}
      <header>
        <h2 id="findings-heading">
          {findings.length} {findings.length === 1 ? "passage" : "passages"} worth checking
        </h2>
        <p>Translation notes, not factual checks—read them closely, then judge for yourself.</p>
      </header>
      <div class="findings-list">
        {#each visibleFindings as finding}
          <div class="finding-wrapper" id={`finding-${finding.flag.id}`}>
            <FlagDetails
              flag={finding.flag}
              shadowText={finding.translation.shadow_text}
              locationHref={`#segment-${finding.segment.id}`}
              feedback={feedbackByFlag[finding.flag.id] ?? null}
              on:feedback={(event) =>
                dispatch("feedback", { flagId: finding.flag.id, verdict: event.detail })}
            />
          </div>
        {/each}
      </div>
      {#if findings.length > 4}
        <button
          class="findings-toggle"
          type="button"
          on:click={() => (showAllFindings = !showAllFindings)}
        >
          {showAllFindings ? "Show fewer findings" : `Show all ${findings.length} findings`}
        </button>
      {/if}
    {:else}
      <div class="no-findings">
        <h2 id="findings-heading">No specific changes were flagged.</h2>
        <p>The translation still deserves normal human judgment; this is not a guarantee of accuracy.</p>
      </div>
    {/if}
  </section>

  <section class="article-section" aria-labelledby="translation-heading">
    <header class="article-heading">
      <div>
        <h2 id="translation-heading">
          {activeLanguage ? languageNames[activeLanguage] : "Translation"}
        </h2>
        <p>Read the full translation, with paragraph breaks preserved.</p>
      </div>
      <label class="original-toggle">
        <input type="checkbox" bind:checked={showOriginal} />
        Show original
      </label>
    </header>

    <div class:with-original={showOriginal} class="article-reader">
      {#each paragraphs as paragraph}
        <article class="reader-paragraph">
          {#if showOriginal}
            <div class="original-paragraph">
              <span class="paragraph-label">{languageNames[job.result.source_language]}</span>
              <p lang={job.result.source_language}>
                {#each paragraph.segments as segment}{segment.source_text}{" "}{/each}
              </p>
            </div>
          {/if}
          <div class="translated-paragraph">
            {#if showOriginal && activeLanguage}
              <span class="paragraph-label">{languageNames[activeLanguage]}</span>
            {/if}
            <p lang={activeLanguage ?? undefined}>
              {#each paragraph.segments as segment}
                {@const translation = translationFor(segment, activeLanguage)}
                {#if translation}
                  <span
                    id={`segment-${segment.id}`}
                    class:flagged-sentence={translation.flags.length > 0}
                  >
                    {translation.text}
                    {#if translation.flags.length}
                      <a
                        class="sentence-marker"
                        href={`#finding-${translation.flags[0].id}`}
                        aria-label={`${translation.flags.length} findings for this sentence`}
                      >
                        {translation.flags.length}
                      </a>
                    {/if}
                  </span>{" "}
                {/if}
              {/each}
            </p>
          </div>
        </article>
      {/each}
    </div>
  </section>

  {#if activeLanguage}
    <section class="passage-review" aria-labelledby="passage-review-heading">
      <div>
        <h2 id="passage-review-heading">
          Was the {languageNames[activeLanguage]} translation useful?
        </h2>
        <p>Your answer helps separate useful warnings from noise.</p>
      </div>
      <div class="review-verdicts">
        {#each [
          ["helpful", "Yes"],
          ["incorrect", "No"],
          ["unsure", "Unsure"]
        ] as option}
          <button
            class:chosen={overallVerdicts[activeLanguage] === option[0]}
            type="button"
            aria-pressed={overallVerdicts[activeLanguage] === option[0]}
            on:click={() => chooseOverallVerdict(option[0] as FeedbackVerdict)}
          >
            {option[1]}
          </button>
        {/each}
      </div>

      {#if overallVerdicts[activeLanguage] === "incorrect"}
        <label for={`missed-issue-${activeLanguage}`}>
          What changed or went missing?
        </label>
        <textarea
          id={`missed-issue-${activeLanguage}`}
          value={missedIssues[activeLanguage] ?? ""}
          on:input={(event) =>
            (missedIssues = {
              ...missedIssues,
              [activeLanguage as Language]: event.currentTarget.value
            })}
          maxlength="1000"
          rows="3"
          placeholder="Point to a word, claim, or nuance."
        ></textarea>
        <button
          class="primary-action"
          type="button"
          disabled={feedbackState[activeFeedbackId] === "saving"}
          on:click={() => savePassageReview(activeLanguage as Language)}
        >
          {feedbackState[activeFeedbackId] === "saving" ? "Saving…" : "Save review"}
        </button>
      {/if}

      {#if feedbackState[activeFeedbackId] === "saved"}
        <span class="save-status" role="status">Review saved.</span>
      {:else if feedbackState[activeFeedbackId] === "error"}
        <span class="save-error" role="alert">Couldn’t save. Try again.</span>
      {/if}
    </section>
  {/if}
</section>
