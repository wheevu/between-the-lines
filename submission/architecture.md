# Architecture and data flow

## Reader workflow

```text
article text or bounded public URL
  │
  └─ Gemini: one reader-selected aligned translation + grounded language notes
       │
       └─ deterministic number, negation, and protected-fact checks
       │
       ▼
reader inspects the translation and optionally chooses one quoted claim
       │
       ├─ Gemini: EN/VI/KO query generation
       ├─ Fact Check Tools API, when configured: reviewed-claim discovery
       └─ Gemini Google Search grounding: public URL discovery
              │
              ▼
       bounded local page extraction
              │
              ├─ canonicalize, exclude self, cap publishers/pages
              ├─ exact and near-duplicate grouping
              └─ local E5 passage ranking via PyTorch or OpenVINO
                     │
                     ▼
       top excerpts → literal claim alignment + meaning-delta comparison
                     │
                     ▼
       credited-origin lineage grouping
                     │
                     ▼
       deterministic independent-lineage evidence quorum
                     │
                     ▼
reader inspects sources, limitations, and records corrections
```

## Why AI is used

- Translation and context-sensitive language notes require multilingual
  generation.
- Multilingual E5 retrieves semantically related evidence passages across
  three languages and conservatively helps match differently written
  credited-origin names.
- Structured stance comparison distinguishes support, challenge, context, and
  mismatch in exact excerpts.
- Claim facets preserve attribution, modality, and legal state before search.
- Source-lineage grouping prevents translated or syndicated repetitions from
  counting as independent confirmation.

The AI does not choose the reader’s claim or override minimum-evidence rules.
It may identify an explicitly credited origin; deterministic grouping and
minimum-evidence logic decide how that origin affects independence.

## Why local inference matters

- E5 evidence ranking and credited-origin alias matching run on the laptop.
- Most fetched page content stays local; only selected excerpts reach Gemini.
- The same E5 path can run with PyTorch or OpenVINO.
- Bounded work fits the 16 GB development machine: one claim, 12
  pages and 80 candidate passages per claim.

This is partly local, not offline, because Gemini and public search remain
network dependencies. NLLB is an offline experimental comparator only; tests
showed it was too slow for the interactive path.

## Persisted state

SQLite stores:

- analysis job, source-aligned results, and reviewer feedback;
- source-grounded claim candidates and explicit selection;
- generated search queries;
- selected evidence excerpts, canonical URLs, publisher identity, dates,
  language, content hash, cluster, relevance, stance, and limitations;
- fact-check feedback.

Full fetched evidence pages are not persisted.

The separate frozen evaluation runner writes an atomic JSON checkpoint, not
SQLite rows. It binds completed claim results and runtime records to hashes of
the corpus, candidate pool, selection, adjudication, and pipeline. It resumes
only when those inputs and the model/backend settings are unchanged.

## Failure boundaries

- Article extraction, model generation, discovery, page reading, ranking, and
  comparison are separate stages.
- One failed page produces a recorded limitation.
- Too little independent evidence produces “still unresolved.”
- A model comparison that cannot quote the source literally is downgraded per
  excerpt; it does not invalidate other valid excerpts in the same batch.
- Completed earlier claims remain visible if a later claim fails.
- The browser resumes a stored job through its URL.
- The evaluation runner pauses at provider quota exhaustion without counting
  that attempt as an evaluated `insufficient` claim.
