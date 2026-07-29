# Stress-test baseline — 25 July 2026

This baseline freezes the result before the selective-verification and quick-view
experiments. It uses all 24 known-source claim cases: eight source claims in each
of English, Vietnamese, and Korean, across six topics.

## Result

| Measure | Baseline |
|---|---:|
| Cases | 24 |
| Supported | 7 (29.2%) |
| Conflicting | 0 |
| Unresolved / insufficient | 17 (70.8%) |
| Cases with two readable articles | 15 (62.5%) |
| Cases with two independent lineages | 13 (54.2%) |
| Cases with at least one aligned passage | 16 (66.7%) |
| Cases with no readable article | 4 (16.7%) |
| Cases with a retrieval failure | 2 (8.3%) |
| Median runtime | 5.49 s |
| 95th-percentile runtime | 8.41 s |
| Supported without two lineages | 0 |
| Supported without aligned evidence | 0 |

The system is conservative: it did not produce a supported verdict without both
independence and alignment. Its limiting factors are coverage and alignment. Two
articles alone are not enough; only 13 of the 15 two-article cases formed two
lineages, and several readable cases produced no aligned passage.

## Interpretation limits

- This is a closed, known-source test. It does not measure open-web discovery.
- Eighteen non-pilot cases use generic frozen claim facets. The run is useful for
  retrieval, alignment, lineage, and status safety, but not for judging automated
  attribution or modality extraction.
- “Insufficient” is a successful safety outcome when evidence is missing,
  dependent, or poorly aligned. It must not be optimized away to improve the
  apparent verdict rate.
- The full machine-readable result is
  `claim-trace-closed-set-full.json`; scoring rules are frozen in
  `stress-test-scorecard-v1.json`.

## Answerability-adjusted audit — 26 July

The raw 16/24 aligned-case count was not a valid recall denominator. An author
review of both permitted comparison articles found 18 answerable cases and six
source-specific cases whose comparison set contained no matching passage.

The retrospective stage audit finds that previously identified anchors survive
extraction, chunking, and ranking in 18/18 answerable cases. Strict alignment is
16/18; counting one partial alignment gives 17/18. Because 16 anchors were
seeded from stored system output, these are localization results, not unbiased
recall. A separately pre-frozen balanced 12-case publisher holdout reaches
10/12 ranking@6 (83.3%), with one transient extraction failure and one passage
excluded by the two-per-publisher diversity cap.

These are author-reviewed development results, not independent accuracy. The
artifacts and decision not to change production ranking are documented in
`claim-trace-recall-report-2026-07-26.md`.

## Selective local-verification experiment

The original local NLLB shadow-translation design was too slow for the
interactive path. On one article per source language, checking 20 of 52 segments
still took 88.90 seconds after direction-specific warm-up. It was 2.12 times
faster than checking every segment, but nowhere near the product latency target.

An intermediate experiment replaced NLLB with risk-routed multilingual E5.
Across 12 balanced real articles:

| Measure | Result |
|---|---:|
| Segments | 248 |
| Locally compared | 115 (46.37%) |
| Selective E5 median-time sum | 1,527 ms |
| Full E5 median-time sum | 3,215 ms |
| Local-stage speed-up | 2.10× |

The adversarial check rejected this intermediate design. On the 18 controlled
translation pairs, direct E5 similarity overlapped heavily between clean and
deliberately changed translations (roughly 0.81–0.90), so speed did not make it
a defensible meaning detector.

The shipped quick path therefore makes one selected-target Gemini call, applies
deterministic protected-fact checks to every passage, retains source-grounded
model notes, and makes zero blocking NLLB or E5 calls. Local E5 remains in Claim
Trace passage ranking, where it has a defined retrieval task. The experiment
artifacts remain as negative engineering evidence:
`selective-verification-m1.json` and `selective-embedding-m1.json`.
