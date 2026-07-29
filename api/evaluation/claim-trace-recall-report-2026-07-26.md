# Claim Trace answerability and recall audit

Date: 26 July 2026  
Reviewer role: author  
Machine: Apple M1 MacBook Air, 16 GB

## Why the denominator changed

The original stress-test headline counted 16 of 24 cases with a strictly
aligned passage. That count was useful as a raw system outcome, but it was not
recall: six source-specific claims had no matching passage in either permitted
comparison article. Rewarding alignment on those cases would reward an
over-broad or invented match.

The new oracle records both comparison articles for every case, short exact
gold passages for answerable cases, and a rationale for unanswerable cases.
Sixteen anchors were seeded from stored aligned output; two missed answerable
cases and six unanswerable cases were manually audited against current pages.
The core result is therefore a retrospective stage diagnostic, not an unbiased
retrieval or alignment score.

## Core 24-case diagnostic

| Stage | Passed | Eligible | Rate |
|---|---:|---:|---:|
| Previously identified answerable source extracted | 18 | 18 | 100% |
| Retrospective anchor survived chunking | 18 | 18 | 100% |
| Retrospective anchor selected by ranking | 18 | 18 | 100% |
| Retrospective strict alignment | 16 | 18 | 88.9% |
| Retrospective aligned or partially aligned | 17 | 18 | 94.4% |

Six other cases were correctly excluded from the recall denominator because
their comparison articles did not contain the frozen claim. One WMO case
reached Gemini at raw rank 1 but remained unanchored; one World Cup compound
claim received only a partial alignment. There was no core extraction,
chunking, or ranking miss.

## Publisher-held-out retrieval check

The separate 12-case set uses only robustness-corpus publishers. Its exact
passages and any/all compound-match policy were frozen before the diagnostic
run. It contains four claims per source language and two per topic.

| Stage | Passed | Eligible | Rate |
|---|---:|---:|---:|
| Held-out source extracted | 11 | 12 | 91.7% |
| Gold passage survived chunking | 11 | 12 | 91.7% |
| Gold passage selected by ranking | 10 | 12 | 83.3% |

The two misses were heterogeneous. One Korean WMO page became unreadable. One
Hantavirus passage ranked third within its only publisher and was excluded by
the two-passages-per-publisher diversity cap. The latter is a conservative
tradeoff, not evidence for weakening source diversity across the product.

## Decision

Do not add a reranker, vector database, or new chunking strategy. The unbiased
publisher holdout clears the frozen 80% retrieval target, and no failure stage
repeats often enough to justify a production change. The core diagnostic shows
that already-identified anchors survive the earlier pipeline. The next
technical investigation, if pursued, should be the single WMO
literal-alignment miss—not retrieval recall.

Artifacts:

- `claim-trace-recall-oracle-v1.json`
- `claim-trace-recall-diagnostic-v1.json`
- `claim-trace-publisher-holdout-v1.json`
- `claim-trace-publisher-holdout-result-v1.json`

Neither diagnostic stores full article text. Both are hash-bound to their
corpus and oracle inputs.
