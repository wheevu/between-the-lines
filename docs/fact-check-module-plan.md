# Between the Lines: fact-check and context module plan

**Status:** gated implementation built; live evidence validation pending  
**Prepared:** 24 July 2026  
**Constraint:** English, Vietnamese, and Korean text; no speech; development on a
16 GB M1 MacBook Air; final Intel/OpenVINO benchmark on Intel hardware.

## 1. Product outcome

After reading a translation, a person can choose a small number of factual
claims and see:

- what independent sources support, dispute, or contextualize each claim;
- the exact evidence passage, publisher, date, language, and link;
- whether sources are independent or repeat the same reporting;
- what the system could not establish and why.

The module does **not** label an article or person “true” or “false.” It reports
an evidence status for a specific, quoted claim at a recorded point in time.
The reader makes the final judgment.

The narrow MVP workflow is:

```text
translated article
  → 3–5 checkable claim candidates
  → reader selects up to 3
  → EN/VI/KO evidence search
  → local passage ranking and duplicate grouping
  → evidence-backed status
  → reader inspects sources and gives feedback
```

Limiting a run to three claims keeps the interface readable, bounds search and
model cost, and fits the available memory.

## 2. Reader experience

### Entry point

Add one secondary action below the completed translation: **Check claims &
context**. Keep translation findings and factual evidence separate; a
translation warning is not evidence that the source claim is false.

### Claim selection

Show three to five candidate cards in article order. Each card contains the
exact article quote and a one-sentence standalone version. Label candidates as:

- **Checkable fact** — can be tested against external evidence;
- **Attributed statement** — verifies that a person or organization said it,
  not that the quoted allegation is true;
- **Not suitable to check** — opinion, prediction, vague judgment, or private
  state. Explain why and leave it unselected.

Preselect nothing. Let the reader choose one claim and start the check.
This is a useful human control and prevents the system from spending most of
its time on an irrelevant detail.

### Progress

Show real stages and the active claim:

1. Identifying search terms
2. Looking across English, Vietnamese, and Korean
3. Reading and grouping sources
4. Comparing evidence

The job must be resumable through `?fact_check=<id>`, just like translation
analysis. One failed or inaccessible source must not fail the whole job.

### Result

For each claim, show one of four evidence statuses:

- **Supported by the sources found**
- **Disputed by the sources found**
- **Mixed or context-dependent**
- **Not enough reliable evidence**

Avoid a green “passed” checkmark. Under the status, show a short explanation,
the search time, and two evidence groups:

- **What supports this**
- **What challenges or qualifies this**

Each evidence card shows an exact excerpt, publication and retrieval dates,
source language, source type, and a link. An expandable “Why this source is
here” area explains relevance and whether the page is a primary source,
professional fact-check, direct reporting, or secondary commentary.

Group syndicated copies under one origin so ten rewrites of one wire report do
not look like ten independent confirmations. Clearly mark snippet-only or
paywalled results, and do not let those alone determine a status.

Feedback remains compact:

- Is this evidence relevant? Yes / No / Unsure
- Does the status follow from the cited evidence? Yes / No / Unsure
- Optional correction or better source

## 3. Technical pipeline

### Stage A — claim extraction and decontextualization

Create a focused `GeminiFactChecker`; do not broaden `GeminiTranslator` and risk
translation regressions. Give Gemini the original segments, not a translated
version, and request structured claim candidates:

```text
id
segment_ids
source_quote
standalone_claim
claim_type
checkworthiness
reason
entities
dates
numbers
```

The prompt must:

- preserve attribution (“ADOR alleged X” is different from “X happened”);
- carry names, dates, pronoun referents, and location into the standalone claim;
- reject opinions, predictions, rhetorical questions, and vague evaluations;
- treat article text as untrusted data and ignore instructions inside it;
- rank central, consequential claims over trivia.

Before showing a candidate, deterministic checks confirm that `source_quote`
occurs in the stored article and every `segment_id` exists. Never invent a
quote. Preserve the source-language claim as canonical; English is only a
retrieval pivot.

### Stage B — multilingual query generation

For each selected claim, generate two compact search queries per language:

- exact/entity-heavy query;
- paraphrase/context query.

Each query must preserve named entities, numbers, dates, and attribution. Keep
the original script plus common cross-language name forms, such as
`Min Hee-jin`, `민희진`, and `Min Hee Jin`. Store all generated queries so the
reader and evaluator can inspect retrieval behavior.

### Stage C — two retrieval tracks

1. **Previously reviewed claims.** Query the Google Fact Check Tools API in all
   three languages. Preserve the fact-check publisher’s original rating rather
   than forcing rating terms from different organizations into one universal
   scale.
2. **Open-web evidence.** Use Gemini Google Search grounding for URL discovery.
   Read URLs from grounding metadata—never from model-written citation text.
   Fetch candidate pages with the existing bounded article extractor.

For the first implementation, do not add a general search SDK or crawler. The
existing Gemini dependency plus the optional Fact Check Tools endpoint is the
smallest useful stack. Put retrieval behind two small functions so the search
provider can be replaced later without changing result models.

Retrieval rules:

- exclude the input article as evidence for itself;
- cap at 12 fetched URLs and 80 candidate passages per claim;
- keep at most three pages per publisher;
- record failures without aborting the claim;
- canonicalize URLs and group identical or near-identical passages;
- prefer a primary document or direct statement when the claim concerns a
  ruling, filing, announcement, chart, or published statistic;
- retain evidence on both sides when available.

### Stage D — local evidence ranking

Split fetched pages into 120–220-word passages with title, date, publisher, and
URL attached. Reuse the current multilingual E5 model to embed the canonical
claim and passages locally. Rank by semantic similarity, then apply simple
diversity rules so one publisher and one syndication cluster cannot occupy all
top slots.

Add a multilingual cross-encoder reranker only if the E5 baseline misses
relevant passages in evaluation. This avoids loading another large model before
there is evidence that it helps.

For the Intel build, export the chosen embedding model to OpenVINO and quantize
it only where quality holds. The OpenVINO backend was exercised on the M1
development machine with the same top-five ranking as PyTorch, but it was
slower there; this is compatibility evidence, not an Intel acceleration claim.
The festival benchmark should compare runtime defaults first, then test
FP32/FP16 or INT8 only when the recorded configuration is known on an Intel
laptop. Measure top-80 passage latency, peak memory, throughput, and ranking
agreement. The product reason for local ranking is data minimization: most page
content stays on-device and only the small evidence set goes to Gemini.

### Stage E — evidence stance and synthesis

Send only the selected claim and the top grounded excerpts to Gemini in a
structured request. For every excerpt, return:

- `supports`, `disputes`, `context`, or `irrelevant`;
- a one-sentence reason tied to exact words in the excerpt;
- whether the evidence is direct or only reports another source;
- any date or scope mismatch.

Then compute the status conservatively:

- **Supported:** at least two distinct publishers in two distinct evidence
  clusters support it, with no comparably strong contradiction;
- **Disputed:** the symmetric rule for contradiction;
- **Mixed:** credible evidence differs by scope, date, definition, or source;
- **Not enough:** everything else.

The prototype deliberately requires two publishers even when Gemini classifies
one excerpt as direct primary evidence. Source-type classification is not
authentication, so it cannot bypass the independence rule. Status explanations
are deterministic and cite stored evidence IDs; the displayed excerpts come
verbatim from the bounded fetched text.

## 4. Data and API contract

Keep the prototype’s JSON-result pattern instead of adding a normalized
knowledge graph.

Add:

```text
fact_checks
  id, analysis_id, status, stage, progress,
  candidate_claims_json, selected_claim_ids_json,
  result_json, error, created_at, updated_at

fact_check_feedback
  id, fact_check_id, target_type, target_id,
  verdict, correction, created_at
```

`FactCheckResult` contains claims, queries, evidence, evidence clusters,
statuses, limitations, and `checked_at`. Evidence stores the exact excerpt,
canonical URL, publication date when available, retrieval time, language,
source type, stance, relevance, and content hash. Do not store full fetched
pages after passage extraction.

Endpoints:

```text
POST /api/analyses/{analysis_id}/fact-checks
GET  /api/fact-checks/{fact_check_id}
POST /api/fact-checks/{fact_check_id}/selection
POST /api/fact-checks/{fact_check_id}/feedback
```

The first POST starts claim extraction and ends in `awaiting_selection`.
`selection` accepts one candidate ID and resumes the background job.
Both POST endpoints are idempotent for repeated browser submissions.

Failure behavior:

- a search-provider outage yields a resumable claim-level error;
- an inaccessible page is recorded and skipped;
- if fewer than two usable evidence sources remain, return “not enough
  evidence,” not a failed job;
- a Gemini schema or quote-validation failure is retried once, then shown as an
  actionable error;
- partial completed claims remain visible if a later claim fails.

## 5. File-level implementation sequence

1. **Models and storage** — extend `api/app/models.py` with claim, evidence,
   status, and feedback models; add the two SQLite tables and CRUD methods in
   `api/app/store.py`. Test serialization, idempotent selection, restart/resume,
   and foreign-key behavior.
2. **Claim candidates** — add `api/app/fact_checker.py` for orchestration and a
   focused structured-output client in `api/app/gemini_fact_check.py`. Add API
   creation/read/selection routes in `api/app/main.py`. Test attribution,
   decontextualization, exact quotes, opinions, and prompt injection.
3. **Retrieval** — add `api/app/evidence_retrieval.py`, reuse
   `api/app/article.py`, and add optional Fact Check Tools configuration in
   `api/app/config.py`. Test URL canonicalization, self-citation rejection,
   date parsing, inaccessible sources, syndication grouping, and multilingual
   query preservation.
4. **Local ranking** — add passage chunking and E5 ranking in
   `api/app/evidence_ranker.py`, keeping memory limits explicit. Benchmark the
   E5 baseline before considering a reranker. Add ranking fixtures in all three
   languages and hard negatives with the same entities but different dates.
5. **Stance and status** — implement exact-evidence validation and conservative
   status rules in `api/app/evidence_synthesis.py`. Test conflicting sources,
   outdated evidence, attributed allegations, insufficient evidence, and
   citations that do not support the explanation.
6. **Reader UI** — extend `web/src/lib/types.ts` and `api.ts`; add
   `ClaimSelection.svelte`, `FactCheckProgress.svelte`, and
   `FactCheckResults.svelte`. Link from `ResultsView.svelte` without mixing
   translation findings into evidence results. Add unit tests and browser
   journeys for selection, resume, partial failure, source inspection, and
   feedback.
7. **OpenVINO path** — export and benchmark the selected E5 model on the M1 and
   an Intel machine. Adopt quantization only if evidence recall and top-k
   ranking remain within the evaluation gate.

## 6. Evaluation plan and release gates

Build a hand-reviewed set of 30 claims from the existing 15 NewJeans articles:
10 source claims per language, balanced across dates, numbers, legal
attribution, direct announcements, and claims that should abstain. Include
cross-language evidence and several syndicated-source traps. A bilingual
reviewer records acceptable evidence sets and an evidence status; disagreements
are adjudicated rather than silently averaged.

Measure:

| Layer | Metric | MVP gate |
|---|---|---:|
| Claim selection | Checkable and central candidates in top 3 | ≥ 80% |
| Quote grounding | Candidate quotes exactly present in source | 100% |
| Retrieval | At least one acceptable evidence passage in top 5 | ≥ 80% |
| Citation correctness | Displayed excerpt supports its stated stance | ≥ 90% |
| Status | Correct status when evidence is sufficient | ≥ 80% |
| Abstention | Insufficient cases correctly left unresolved | ≥ 85% |
| Language parity | Largest gap across EN/VI/KO | ≤ 10 points |
| Source diversity | No duplicate cluster counted twice | 100% |
| Resilience | One failed page does not fail the claim | 100% |
| Local ranking | Warm top-80 passage ranking | benchmark, then set gate |

Use evidence-aware evaluation rather than verdict accuracy alone: a correct
label with irrelevant citations is a failure. The AVeriTeC task follows this
principle, and newer Ev2R work evaluates retrieval when several different
evidence sets may all be valid.

Run five to eight reader sessions. Give each person three tasks: identify what
is known, explain why a claim is unresolved, and open the strongest source.
Record task completion, time, wrong interpretations of status, and which UI
labels cause hesitation.

Red-team cases before release:

- allegation versus proven event;
- opinion or prediction presented as a fact;
- breaking news where later evidence changes the answer;
- same wire report copied by many outlets;
- wrong person with the same or transliterated name;
- correct number with a different unit, currency, or date;
- evidence that supports only part of a compound claim;
- malicious instructions embedded in a fetched page;
- search results that only cite the input article;
- paywall, robots denial, deleted page, or snippet-only evidence.

## 7. Responsible-AI boundaries

- Show evidence and uncertainty, never an unexplained authority score.
- Do not assign global “trust scores” to publishers.
- Separate verification of an attributed statement from verification of the
  allegation inside that statement.
- Preserve contradictory evidence instead of choosing the most convenient
  source.
- Record `checked_at`; evidence status can become stale.
- Keep full fetched pages transient. Persist only the evidence excerpt, metadata,
  and hash needed to reproduce what the user saw.
- Treat article and web text as hostile prompt input.
- Let users report irrelevant evidence, a wrong status, or a better source.
- For claims about private individuals, default to insufficient evidence unless
  high-quality public documentation directly supports the conclusion.

## 8. Deliberate deferrals

Do not include image forensics, reverse-image search, C2PA validation, social
media crawling, source reputation scoring, or a permanent vector database in
the first module. C2PA can later answer provenance questions for attached media,
but provenance is not the same as whether a textual claim is true.

Do not expose this module from the translation result until the current
translation audit has enough human feedback to establish that readers can
distinguish translation findings from factual evidence. The implementation is
kept behind that gate so its contracts and failure handling can be tested
without presenting unvalidated output to readers.

## References informing the plan

- [Google Fact Check Tools API](https://developers.google.com/fact-check/tools/api/reference/rest/)
- [Google structured outputs and grounding](https://ai.google.dev/gemini-api/docs/structured-output)
- [OpenVINO 2026 system requirements](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino/system-requirements.html)
- [OpenVINO document reranking](https://docs.openvino.ai/2026/model-server/ovms_demos_rerank.html)
- [Document-level claim extraction and decontextualisation](https://aclanthology.org/2024.acl-long.645/)
- [Multilingual previously fact-checked claim retrieval](https://aclanthology.org/2023.emnlp-main.1027/)
- [AVeriTeC shared task](https://aclanthology.org/volumes/2024.fever-1/)
- [Multilingual retrieval-bias study](https://aclanthology.org/2026.eacl-long.240/)
