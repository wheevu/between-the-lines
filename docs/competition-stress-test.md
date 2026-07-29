# Between the Lines: competition and product stress test

Prepared: 25 July 2026

## Verdict

The idea holds up only with a narrower identity:

> A three-language news reader that shows where translation can change a claim,
> then traces one reader-selected claim through independent reporting.

It should not be pitched as an automatic fact-checker, a general news
aggregator, or a better translator. Those categories have mature competitors
and would make the current evidence look thin.

## Competitive boundary

| Product | What it already does well | Boundary for Between the Lines |
|---|---|---|
| Google Translate | Fast general translation at enormous language scale | Explain claim-level meaning risk in one EN/VI/KO news workflow |
| Ground News | Clusters broad coverage and compares political/source perspectives | Compare wording, attribution, dates, numbers, and source reuse across three languages |
| Full Fact AI | Monitors large media streams, classifies checkable claims, and matches repeats for professional fact-checkers | Serve an individual reader examining one article and one claim |
| Google Pinpoint | Searches and analyzes large uploaded document collections for journalists | Begin from a public article URL and return a small reading decision, not a research workspace |
| Fact Check Explorer | Finds already-published ClaimReview fact checks | Trace current multilingual reporting even when no prior fact check exists |

Official references:

- Ground News explains that its Bias Comparison summarizes left, center, and
  right coverage and may be unavailable without enough distinct coverage:
  https://help.ground.news/en/articles/3189505
- Full Fact describes sentence-level claim classification, repeat matching, and
  human fact-checker workflows:
  https://fullfact.org/ai/
- Google describes Pinpoint as search and AI over large private document
  collections:
  https://journaliststudio.google.com/pinpoint/about/en-GB_uk/

## Festival pressure test

The 2024 and 2025 Intel winners repeatedly combine a specific beneficiary,
visible human action, technical implementation, responsible AI, and evidence of
deployment or validation. Accessibility, health, education, agriculture, and
local/private inference are common. The 2025 global winners include an
Intel-optimized offline educational RAG assistant and OpenVINO navigation
glasses; Vietnam’s global winner addressed sign-language communication. The
2024 Vietnam winner, Aero ResQ, addressed emergency response.

References:

- https://www.intel.com/content/www/us/en/corporate/artificial-intelligence/winner2025.html
- https://www.intel.com/content/www/us/en/corporate/artificial-intelligence/winners2024.html

The project’s advantages are:

1. EN/VI/KO is a coherent cross-border student use case, not arbitrary
   multilingual breadth.
2. It exposes exact phrases instead of assigning opaque article truth or bias
   scores.
3. It models source independence, so repeated wire copy does not look like
   corroboration.
4. It abstains when coverage or alignment is inadequate.
5. The local E5 evidence-ranking stage is small enough for ordinary hardware
   and can be measured with OpenVINO.

Its disadvantages are substantial:

1. News literacy has less immediate visual/emotional impact than accessibility
   or health projects.
2. Open-web retrieval is brittle and quota-dependent.
3. “Fact-checking” creates a high proof burden that the current author-led
   evaluation cannot meet.
4. Translation quality and evidence quality both need strong bilingual human
   review.
5. A URL reader is useful occasionally, not necessarily habit-forming.

## Evidence from the current stress test

- The 24-case known-source run returns 7 supported and 17 insufficient cases.
- It never returns supported without two independent lineages and aligned
  evidence.
- The raw run produced a strictly aligned passage in 16/24 cases. A subsequent
  answerability audit found only 18 cases contained a matching comparison
  passage. A retrospective diagnostic localizes the remaining outcomes to one
  partial and one failed literal alignment; it is not an unbiased recall score
  because most anchors came from stored system output.
- A balanced publisher-held-out retrieval set reaches 10/12 at ranking@6. Its
  misses are one unreadable page and one passage excluded by the conservative
  per-publisher diversity cap, so no new reranker was added.
- The original NLLB shadow pass is not viable interactively on the M1 Air.
- Risk-routed E5 was fast, but a controlled probe showed overlapping similarity
  scores for clean and broken translations. It was removed from the translation
  path rather than presented as a second opinion.
- The 120-URL robustness shell is balanced by language, but only 101/120 are
  immediately ready and five additions are off-event or peripheral by title.

## Product test

The software has a credible first-use loop:

```text
paste URL → choose article language → choose “Read in”
→ readable translation → inspect passages worth checking
→ optionally trace one claim → inspect evidence and limitations
```

The likely repeat use is not “fact-check every article.” It is:

- reading a Korean or Vietnamese article for class;
- checking a consequential number, legal state, quote, or timeline;
- comparing how the same regional event is framed across languages.

The product fails if users interpret “no warning” as “accurate,” or
“insufficient” as “false.” The reader study must test those two
misinterpretations directly.

## Direction

Continue, but narrow:

- Keep one selected target language in the fast path.
- Keep Claim Trace optional and limited to one selected claim.
- Lead with “what changed across languages,” not “AI fact-checker.”
- Treat the 36-article core and 120-URL robustness shell as separate evidence.
- Use local E5 for evidence ranking, not as an uncalibrated translation judge.
- Do not add source ratings, a social feed, image forensics, speech, or a large
  vector database before the reader and bilingual gates pass.

The next decisive evidence is five reader sessions and independent review of a
small balanced set. More code is not the current bottleneck.
