# Robustness-corpus review — 25 July 2026

The robustness shell contains 120 URLs across 12 event clusters and six topics:
40 English, 40 Vietnamese, and 40 Korean. It retains the 36-article frozen core
and adds 84 publisher-resolved discovery candidates. It is not a gold set.

## Automated preflight

| Measure | Result |
|---|---:|
| URLs | 120 |
| Extracted | 105 |
| Ready without intervention | 101 (84.17%) |
| Failed extraction | 15 |
| Over 2,500 words | 3 |
| Language mismatch | 1 |
| Exact date metadata | 89 |
| Date mismatch | 15 |
| Title match | 100 |

Readiness by source language is 32/40 English, 32/40 Vietnamese, and 37/40
Korean. Health is the weakest topic at 15/20 ready; culture/sports and
technology/economy are strongest at 18/20.

## Author title review of the 84 additions

Most additions are on-event from their titles. The following should not enter a
factual score without replacement:

- `vietnam-ai-law-effective-vi-robust-2`: concerns the EU AI Act, not the
  Vietnamese law.
- `wmo-five-year-temperature-outlook-vi-robust-2`: an El Niño warning, not
  clearly the frozen five-year WMO outlook.
- `winter-olympics-opening-2026-vi-robust-3`: closing ceremony rather than
  opening ceremony.

Two are peripheral and useful only as negative retrieval cases:

- `korea-ai-basic-act-implementation-vi-robust-1`: primarily about Vietnam’s
  law, with Korea as comparison.
- `apple-wwdc26-siri-vi-robust-2`: generic WWDC invitation analysis; the title
  does not establish Siri coverage.

This gives 79 title-likely-on-event additions, two peripheral cases, and three
off-event cases. Full-text relevance has not been independently adjudicated.

## Decision

Use the 36-article core for quality claims and the 120-URL shell for robustness:
blocked sites, metadata drift, irrelevant retrieval, long pages, language
detection, and duplicate-lineage behavior. Do not merge their denominators.

Expansion is beneficial after this separation. It reveals failure modes that a
small clean corpus hides, but it would weaken the evaluation if machine-found
articles were silently treated as truth labels.

Artifacts:

- `claim-trace-robustness-corpus.json`
- `claim-trace-robustness-preflight-2026-07-25.json`
