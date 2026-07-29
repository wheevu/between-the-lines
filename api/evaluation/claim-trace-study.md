# Claim Trace multi-topic study

> **Historical architecture:** Translation sections in this study describe an
> earlier two-target workflow. The current reader path uses one selected-target
> Gemini translation, deterministic protected-fact checks, and grounded notes.
> NLLB and direct E5 translation comparison were removed after stress testing;
> E5 remains in Claim Trace for evidence ranking.

**Frozen:** 24 July 2026  
**Machine:** Apple M1 MacBook Air, 16 GB  
**Languages:** Vietnamese, English, Korean

This study tests a narrower proposition than “the system fact-checks news.”
It asks whether the prototype can preserve one claim, find comparable passages,
show material wording differences, and avoid counting translations or wire
copies as independent corroboration.

## Benchmark design

The frozen manifest contains:

- 36 real public articles: 12 per language;
- 12 events across public policy, health, science and climate, technology and
  economy, education and society, and culture and sports;
- one clean and one challenging event per topic;
- three language perspectives per event;
- 24 human-written trace propositions, eight per source language;
- explicit edges for attribution, legal state, forecast modality, numbers,
  time updates, local framing, syndication, and source lineage.

The manifest stores metadata and test propositions, not article bodies. See
[`claim-trace-corpus.json`](claim-trace-corpus.json).

## Method: a source-lineage evidence quorum

Claim Trace uses a five-part workflow:

1. Freeze one proposition and retain attribution, modality, legal state,
   numbers, and dates as claim facets.
2. Prepare search wording in all three languages while preserving those
   anchors.
3. Rank bounded article passages locally with multilingual E5.
4. Require a literal aligned quotation and record only concrete deltas in
   certainty, scope, attribution, number, date, legal state, or context.
5. Group articles that explicitly credit the same origin before applying the
   two-source evidence rule.

The last step is the central design choice. Two languages do not equal two
independent sources when both repeat WMO, Reuters, NVIDIA, a court filing, or
another shared origin.

## Live ingestion result: 36/36 ready

The concurrent preflight extracted all 36 articles without retaining their
bodies in the report.

| Check | Result |
|---|---:|
| Readable HTML | 36/36 |
| Correct expected language | 36/36 |
| Under the 2,500-word prototype limit | 36/36 |
| Title matched | 36/36 |
| Median extraction time | 0.636 s |
| Machine-readable date matched the visible frozen date | 32/36 |

The four date mismatches were not silently “corrected.” They remain evidence
that page metadata can expose a timezone-shifted date or an unrelated current
page date. The UI now calls this a **page date**, not a verified publication
date.

The first pass was 33/36. It exposed and led to fixes for:

- two sites returning HTTP 403 and one JavaScript-only legal page, replaced
  with readable sources covering the same event;
- one live-feed article exceeding the local word limit, replaced with a
  bounded match report;
- an English-language detector that mistook one accented surname for
  Vietnamese;
- malformed optional timezone metadata crashing an otherwise readable
  Vietnamese article.

Raw result:
[`claim-trace-preflight-2026-07-24.json`](claim-trace-preflight-2026-07-24.json).

## Closed-set Claim Trace pilot

Six cases—one per topic and two per source language—were run against the two
known cross-language companion articles for the same event. Search discovery
was deliberately excluded so the test isolates ranking, alignment, source
lineage, and conservative status behavior.

| Outcome | Cases |
|---|---:|
| Corroborated | 3 |
| Conflicting | 0 |
| Unresolved | 3 |
| Literal aligned evidence items | 10 |
| Concrete meaning deltas | 1 |

The corroborated cases were Vietnam’s AI-law effective date, a WHO-attributed
hantavirus risk statement, and Spain’s 2026 World Cup final result. The three
unresolved cases were not counted as failures by default: they included
one-lineage repetition, passages that described an announcement without
matching the frozen proposition, and coverage of a different local
institution.

The WMO case is the clearest demonstration. The English WMO page and Korean
report both supported the probability claim but credited the same organization
as “World Meteorological Organization” and “세계기상기구(WMO).” A literal
acronym bridge grouped them, so Claim Trace showed **two articles, two
languages, one independent lineage** and remained unresolved rather than
manufacturing corroboration.

The pilot surfaced one scope delta in post-match World Cup coverage. This is
not a precision or recall measurement. These six propositions were mostly core
facts, and several risk-rich passages failed the literal-alignment gate. The
remaining 18 frozen propositions and independent review are still needed to
measure delta quality.

Raw result:
[`claim-trace-closed-set-pilot.json`](claim-trace-closed-set-pilot.json).

## Live failures that changed the product

- A forecast phrased as “is predicted to” was initially typed as an asserted
  fact. Forecast markers were added for English, Vietnamese, and Korean, and
  regression tests now require forecast claims to stay future/attributed.
- One paraphrased “exact quote” initially invalidated an entire model batch.
  Validation now fails closed per excerpt: a high-similarity punctuation or
  spacing drift can be anchored back to the exact source sentence; otherwise
  that item becomes context with an uncertain match.
- The result page no longer says “no wording difference” when nothing aligned.
  It says that no passage was reliable enough to compare.
- When several articles collapse into one credited origin, the UI explains why
  the article count and independent-lineage count differ.
- A passage-level cluster count could exceed the number of articles. Trace
  summaries now count at article level, while a credited lineage propagates to
  every selected passage from that article.
- Model-supplied credited origins are discarded unless the source name is
  literally present in the stored excerpt. Cross-script organization names can
  merge only through a shared literal acronym such as WMO or WHO, or the
  existing high similarity gate.
- Page-date metadata is treated as unverified. Relative dates remain uncertain
  unless the excerpt itself corroborates the date.
- The API now enforces the same one-claim-at-a-time contract as the interface.
- Google Search grounding returned quota exhaustion in the live discovery
  probe. The app exposes that failure and does not convert it into a factual
  “insufficient” evaluation label.

## Adversarial review

The final design review tried to break the independence and provenance claims.
It found and fixed article/lineage overcounting, ungrounded source-origin
labels, unsafe use of page dates, and an API/UI selection mismatch.

Two risks remain explicit rather than hidden:

- uncredited or undetected syndication can still look independent, so every
  multi-article result carries that limitation;
- live open-web discovery is not validated because the configured provider
  returned quota exhaustion. The closed-set pilot tests only ranking,
  alignment, lineage, and status behavior on known sources.

## M1 efficiency result

The local NLLB shadow is a discrepancy detector; it is not the displayed
translation. On the same 18-segment WMO article, greedy decoding reduced the
full analysis runtime from 131.3 seconds to 78.9 seconds, a 39.9% reduction.
All eight deterministic number flags were retained, and median primary-to-shadow
similarity changed from 0.9448 to 0.9484.

This is a one-article development result. It supports using greedy decoding on
the M1 prototype, not a general speed claim. Raw measurements are in
[`shadow-decoding-m1.json`](shadow-decoding-m1.json).

## What this evidence supports

Supported:

- the 36-source corpus is usable by the bounded extractor on the development
  machine;
- the prototype handles all three languages across six news domains;
- it can preserve literal provenance, abstain, and collapse explicitly shared
  source origins;
- the refined workflow runs within 16 GB on an M1 Air.

Not yet supported:

- general fact-check accuracy;
- meaning-delta recall or precision;
- independent human usefulness;
- complete live search coverage;
- misinformation detection;
- an Intel or OpenVINO speedup claim.

The next evidence step is independent review of the 24 frozen propositions,
including relevance, exact quote, alignment, delta type, origin grouping, and
whether the final status follows from the cited passages.
