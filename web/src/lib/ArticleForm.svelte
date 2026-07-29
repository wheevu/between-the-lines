<script lang="ts">
  import {
    languageNames,
    languages,
    type AnalysisDraft,
    type AnalysisInput,
    type InputMode,
    type Language
  } from "./types";

  export let draft: AnalysisDraft = {
    mode: "url",
    sourceLanguage: "en",
    targetLanguage: "vi",
    text: "",
    url: ""
  };
  export let errorMessage = "";
  export let onDraftChange: (draft: AnalysisDraft) => void = () => {};
  export let onAnalyze: (input: AnalysisInput) => void = () => {};

  let mode: InputMode = draft.mode;
  let sourceLanguage: Language = draft.sourceLanguage;
  let targetLanguage: Language = draft.targetLanguage;
  let textValue = draft.text;
  let urlValue = draft.url;
  let validationMessage = "";

  $: wordCount = textValue.trim() ? textValue.trim().split(/\s+/).length : 0;
  $: availableTargets = languages.filter((language) => language !== sourceLanguage);
  $: if (targetLanguage === sourceLanguage) {
    targetLanguage = availableTargets[0];
  }

  function saveDraft() {
    onDraftChange({
      mode,
      sourceLanguage,
      targetLanguage,
      text: textValue,
      url: urlValue
    });
  }

  function setMode(nextMode: InputMode) {
    mode = nextMode;
    validationMessage = "";
    saveDraft();
  }

  function submit() {
    const value = mode === "text" ? textValue.trim() : urlValue.trim();
    if (!value) {
      validationMessage = mode === "text" ? "Paste an article first." : "Add an article URL first.";
      return;
    }
    if (mode === "url" && !/^https?:\/\//i.test(value)) {
      validationMessage = "Use the full URL, starting with http:// or https://.";
      return;
    }
    if (mode === "text" && wordCount > 2_500) {
      validationMessage = "Keep the article under 2,500 words.";
      return;
    }
    validationMessage = "";
    saveDraft();
    onAnalyze({ mode, sourceLanguage, targetLanguage, value });
  }
</script>

<section class="entry-panel" aria-labelledby="entry-heading">
  <div class="entry-heading">
    <div>
      <h1 id="entry-heading">See what changes in translation.</h1>
      <p>Read an article in English, Vietnamese, or Korean—and check the passages worth a second look.</p>
    </div>
    <p class="privacy-note">
      Gemini translates the article. Claim Trace ranks evidence locally on this device.
    </p>
  </div>

  {#if errorMessage}
    <div class="form-error" role="alert">
      <div>
        <strong>The article wasn’t processed.</strong>
        <p>{errorMessage}</p>
      </div>
      {#if mode === "url"}
        <button type="button" on:click={() => setMode("text")}>Paste the text instead</button>
      {/if}
    </div>
  {/if}

  <div class="mode-switch" aria-label="Article input method">
    <button
      class:active={mode === "url"}
      type="button"
      aria-pressed={mode === "url"}
      on:click={() => setMode("url")}
    >
      Use a URL
    </button>
    <button
      class:active={mode === "text"}
      type="button"
      aria-pressed={mode === "text"}
      on:click={() => setMode("text")}
    >
      Paste text
    </button>
  </div>

  <form on:submit|preventDefault={submit}>
    <label for="source-language">Article language</label>
    <select
      id="source-language"
      bind:value={sourceLanguage}
      on:change={() => {
        validationMessage = "";
        saveDraft();
      }}
    >
      {#each languages as language}
        <option value={language}>{languageNames[language]}</option>
      {/each}
    </select>

    <label for="target-language">Read in</label>
    <select
      id="target-language"
      bind:value={targetLanguage}
      on:change={() => {
        validationMessage = "";
        saveDraft();
      }}
    >
      {#each availableTargets as language}
        <option value={language}>{languageNames[language]}</option>
      {/each}
    </select>

    {#if mode === "text"}
      <div class="field-label">
        <label for="article-text">Article text</label>
        <span class:over-limit={wordCount > 2_500}>{wordCount.toLocaleString()} / 2,500 words</span>
      </div>
      <textarea
        id="article-text"
        bind:value={textValue}
        on:input={() => {
          validationMessage = "";
          saveDraft();
        }}
        rows="8"
        placeholder="Paste the article here."
        aria-describedby="input-hint validation"
        aria-invalid={Boolean(validationMessage)}
      ></textarea>
      <p id="input-hint" class="field-hint">Headlines and photo captions are fine—we clean common paste artifacts.</p>
    {:else}
      <label for="article-url">Article URL</label>
      <input
        id="article-url"
        bind:value={urlValue}
        on:input={() => {
          validationMessage = "";
          saveDraft();
        }}
        type="url"
        placeholder="https://example.com/article"
        aria-describedby="input-hint validation"
        aria-invalid={Boolean(validationMessage)}
      />
      <p id="input-hint" class="field-hint">
        If the site blocks extraction, your URL stays here so you can paste the text instead.
      </p>
    {/if}

    {#if validationMessage}
      <p id="validation" class="field-error" role="alert">{validationMessage}</p>
    {/if}

    <button class="primary-action" type="submit">
      Translate to {languageNames[targetLanguage]}
    </button>
  </form>
</section>
