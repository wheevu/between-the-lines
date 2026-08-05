# Evaluation report — working draft

All figures in this document identify their sample. `[PENDING]` means no
supporting measurement exists yet.

## Prototype scope

Between the Lines accepts English, Vietnamese, or Korean article text or a
bounded public URL. It translates into one reader-selected language, surfaces
exact phrases worth checking, lets a reader select one quoted factual claim,
and finds and compares multilingual evidence while keeping the decision with
the reader.

## Translation and UX evidence

### Fifteen-article NewJeans study

This study records the earlier two-target translation architecture. Subsequent
stress tests rejected both NLLB and direct E5 as live translation-review
signals; the current fast path uses one selected-target Gemini call,
deterministic checks, and grounded notes. The historical results remain here as
development evidence, not as a description of the shipped workflow.

- Corpus: five Vietnamese, five English, five Korean articles published within
  six months of 24 July 2026.
- Six final verification articles: 116 source segments and 232 target-language
  segments.
- Median full-article processing time on the M1 Air: 92.5 seconds.
- Twelve passage reviews cover every language direction twice; all were marked
  helpful by the author.
- The initial warning audit found 12/17 meaning-risk prompts useful (70.6%).
  Four ordinal false positives and one redundant conditional warning were fixed.
- A local rerun preserved the translations and grounded model notes, removed
  those five reviewed false positives, and produced 12/12 useful current
  meaning-risk prompts. The original analyses and rejected judgments remain in
  the database and the rerun mapping is stored in
  `api/evaluation/translation-refinement-2026-07-24.json`.
- These are author judgments, not independent precision evidence.
- Portable raw judgments and the scoped gate output are stored in
  `api/evaluation/translation-feedback.csv` and
  `api/evaluation/translation-readiness-summary.json`.

### Controlled detector fixture

- 18/18 constructed cases pass.
- Purpose: regression coverage for known number, negation, meaning-risk, and
  cultural-note behavior.
- Limitation: constructed cases do not measure real-world translation quality.

### Human translation gate

- Real-news passage reviews: **12/12**, author-reviewed.
- Decided meaning-risk judgments in the current frozen set: **12**.
- Meaning-risk usefulness after documented refinement: **12/12 (100%)**.
- Language-direction passage outcomes: **2/2 helpful in each of EN→VI, EN→KO,
  VI→EN, VI→KO, KO→EN, and KO→VI**.

Conclusion: the continuation gate passes on author review. This supports further
prototype evaluation, not a general translation-accuracy or independently
measured precision claim.

## General-news claim selection

The frozen smoke set contains two recent low-stakes articles per source
language across science, education, culture, and public recreation.

- Articles: 6.
- Frozen candidates after deterministic grounding: 21.
- Candidate range per article: 2–5. One short article retained only two rather
  than padding the set with a candidate that failed grounding checks.
- Exact quote grounding: enforced by generation code and regression tests.
- Added number/date, polarity, future-plan, and metadata failures found during
  iteration were fixed before the final freeze.
- Author candidate judgments: **21/21**.
- Top-three central/checkable success: **6/6 articles (100%)**.
- Per-language top-three result: **2/2 articles in EN, VI, and KO**.
- Reviewer role: **author**; no independent quality claim is made.

The frozen candidates and blank review sheet are:

- `api/evaluation/cross-domain-claim-candidates.json`
- `api/evaluation/cross-domain-claim-review.csv`

Conclusion: the implementation clears the author-reviewed continuation gate
across the three languages. Independent review remains a limitation.

## Claim Trace multi-topic benchmark

The expanded benchmark freezes 36 public articles—12 each in Vietnamese,
English, and Korean—covering 12 events across six domains. Each event has one
article per language and two human-written trace propositions.

Live ingestion on the M1 Air:

- Extracted and ready: **36/36**.
- Expected-language matches: **36/36**.
- Under the 2,500-word bound: **36/36**.
- Title matches: **36/36**.
- Median extraction time: **0.636 seconds**.
- Machine-readable page date matched the manually frozen visible date:
  **32/36**. The UI now labels this as a page date rather than presenting it as
  independently verified publication metadata.

Balanced closed-set Claim Trace pilot:

- Cases: **6**, one per domain and two per source language.
- Corroborated: **3**.
- Unresolved: **3**.
- Conflicting: **0**.
- Literal aligned evidence items: **10**.
- Concrete meaning deltas: **1**.
- Search discovery was excluded so the pilot isolates ranking, literal
  alignment, credited-origin grouping, and status logic.

One WMO case produced two supporting articles in two languages, with the origin
written as “World Meteorological Organization” and “세계기상기구(WMO).” The
literal acronym bridge grouped them into one lineage and the result remained
unresolved. This is a demonstrated abstention and source-independence behavior,
not a fact-check accuracy measurement.

The test exposed and led to fixes for accented-name language detection,
malformed optional publisher metadata, forecast classification in all three
languages, per-excerpt quote anchoring, ungrounded origin labels,
article-level lineage counting, cross-script acronym aliases, page-date
uncertainty, misleading no-difference copy, and article-versus-lineage
explanation.

Raw artifacts and limitations are documented in
`api/evaluation/claim-trace-study.md`.

The later 24-case stress run returned 7 supported and 17 insufficient results,
with no supported result lacking two independent lineages and aligned evidence.
An author answerability audit then found that six source-specific claims had no
matching passage in either permitted comparison article, so raw 16/24 alignment
was not reported as recall. A retrospective stage diagnostic on the 18
answerable cases produced:

- retrospective extraction preservation: **18/18**;
- retrospective chunk preservation: **18/18**;
- retrospective local E5 ranking preservation: **18/18**;
- retrospective strict literal alignment: **16/18 (88.9%)**;
- retrospective aligned or partially aligned: **17/18 (94.4%)**.

A separate balanced publisher-held-out set reaches **10/12 (83.3%)** at
ranking@6. One page was unreadable and one raw-rank-three passage was excluded
by the two-passages-per-publisher diversity cap. These are author-reviewed
development measurements, not independent factual accuracy. Sixteen core
anchors were seeded from stored aligned output, so the core numbers localize
pipeline losses rather than measure unbiased recall. The publisher-holdout
passages were frozen before its run. The audit rejected adding another reranker
because no retrieval failure class repeated.

## Evidence and status evaluation

The gated implementation supports professional fact-check lookup, Google
Search grounding URL discovery, bounded extraction, local ranking, duplicate
grouping, stance comparison, conservative status rules, provenance, partial
failures, and reader feedback.

Current live evidence:

- The 15-article corpus produced a complete pool of 67 candidates: 24
  Vietnamese, 21 English, and 22 Korean.
- Author review and balanced selection from that pool: **67/67**.
- Frozen 30-claim set: **30 claims—10 per language, with two per language in
  each of five categories and all 15 articles represented**.
- Independent gold evidence/status adjudication: **0/30 ready**. The worksheet
  exists and is hash-bound to the selection. Its validator requires two
  distinct reviewers explicitly labeled independent, dated exact excerpts,
  independence notes, and
  documented search scope for an insufficient label.
- A Google Search grounding probe reached the provider but returned HTTP 429
  because free quota was exhausted.
- No Fact Check Tools API key is configured.
- The frozen runner's real gate probe stopped before network use because gold
  evidence adjudication is incomplete and created no system-result artifact.
- Controlled provider, retrieval, ranking, status, and failure tests pass.
- Real-world top-five retrieval recall: **[PENDING]**.
- Citation correctness: **[PENDING]**.
- Status correctness: **[PENDING]**.
- Abstention correctness: **[PENDING]**.

The post-run citation sheet and scorer are implemented. They hash-bind each
final-assessment citation to the frozen result, require relevance, source-text,
and stance judgments, preserve counterexamples, and allow the ≥90% gate only
after every citation has a decided independent review. This is evaluation
infrastructure, not a measured citation result.

No claim has yet passed the independent adjudicated factual-evidence
evaluation. The six-case closed-set pilot is author-run development evidence
and is deliberately reported separately.

## Local ranking and OpenVINO

Development machine: Apple M1 MacBook Air, 16 GB.

| Backend | Warm median | Passages/s | Top-five agreement |
|---|---:|---:|---:|
| PyTorch CPU | 1,703.19 ms | 17.61 | baseline |
| OpenVINO CPU | 2,160.39 ms | 13.89 | 100% |

Both raw results share workload SHA-256
`65d58985a0b7f7f54cd27e8d255a6b4c184f716e698ffba4aa03ad9006483f72`.
Both results use ten measured runs after warmup. The comparison reports a 0.788
Torch-to-OpenVINO speed ratio on this M1, meaning
OpenVINO was slower for this development run.

This proves runtime compatibility and ranking agreement on Apple silicon. It
does not support an Intel performance claim.

Intel Core/Core Ultra measurements: **[PENDING]**.

## Rejected local shadow-decoding experiment

On the same 18-segment WMO article, changing only the local NLLB shadow decoder
from two-beam search to greedy decoding reduced full analysis time from 131.3
seconds to 78.9 seconds (**39.9%**). All eight deterministic number flags were
retained; median primary-to-shadow similarity was 0.9448 before and 0.9484
after.

This one-article M1 measurement led to selective verification tests, but even
the reduced NLLB path remained too slow for interactive use. Controlled probes
also showed that direct E5 similarity could not reliably separate clean
translations from deliberate meaning changes. Both translation-review paths
were removed. The measurements are retained as negative engineering evidence,
not as justification for the current architecture.

## Software verification snapshot: 2 August 2026

These results are a dated verification snapshot, not a current test run.

- Backend: 221 passing tests.
- UI components: 17 passing tests.
- Browser journeys: 8 passing tests, including a keyboard skip-link and focus
  path.
- Python lint, Svelte type checking, production build, Python dependency
  consistency, and production npm audit pass.
- Two upstream deprecation warnings remain: Google GenAI on Python 3.14 and
  Starlette TestClient’s current httpx integration.

These checks establish implementation behavior, not model accuracy.

## Decision

The author-reviewed translation and claim-selection gates pass. The evidence UI
and engine are ready for controlled evaluation after the independent gold key
is complete. The prototype is not ready for factual-quality,
misinformation-detection, general translation-accuracy, independent-review, or
Intel performance claims.
