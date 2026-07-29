# Adversarial review — 25 July 2026

## What was reviewed

The URL-first, single-target EN/VI/KO translation flow; protected-fact warnings;
one-claim multilingual Claim Trace; the 24-case closed set; the 120-URL
robustness shell; and the Intel benchmark path. The design assumes users benefit
from seeing exact wording changes and can understand abstaining evidence.
Open-web discovery accuracy, independent bilingual quality, and Intel-device
performance are not established.

## Blockers

- **Uncalibrated E5 “second opinion.”** Direct source-to-translation scores
  overlapped between clean and deliberately broken controlled pairs. Calling
  this a meaning check would overstate the model. Fixed by removing E5 and NLLB
  from the blocking translation path. E5 remains in evidence ranking, where it
  has a measurable retrieval job. Evidence:
  `api/evaluation/direct-similarity-probe.json`.

## Risks

- **Raw alignment coverage required a denominator audit.** Only 16/24
  closed-set cases contained a strictly aligned passage, but a later author
  audit found six comparison sets contained no matching passage. The separately
  pre-frozen publisher holdout reaches 10/12 at ranking@6. Mitigation: report
  both denominators, keep `insufficient`, and do not market automatic fact
  checking.
- **The large corpus can contaminate quality metrics.** Five of 84 discovered
  titles are off-event or peripheral and 19/120 URLs are not immediately ready.
  Mitigation: keep the 36-article core and 120-URL shell in separate
  denominators.
- **External dependencies are brittle.** Extraction, Gemini quota, search, and
  publisher pages can fail. Mitigation: translation results remain useful
  without Claim Trace; individual retrieval failures do not become verdicts.
- **No reader evidence yet.** Browser tests prove flow mechanics, not
  comprehension. Mitigation: no usability or trust claim before five sessions.
- **No Intel result yet.** The comparator correctly rejects the Apple result.
  Mitigation: retain the Intel Cloud runbook and make no acceleration claim.

## Nice-to-fix

- Replace the 15 blocked robustness URLs to raise extraction coverage without
  changing the gold core.
- Add a small independently reviewed set of hard modality and attribution
  translations before tuning any new detector.
- Record cold and warm end-to-end URL latency, not only isolated model stages.

## Accepted tradeoffs

- A manually selected source language is simpler and more predictable than
  silent language detection.
- Claim Trace checks one claim at a time to keep the evidence decision legible.
- The system stores excerpts and hashes rather than full publisher pages.
- Google News RSS is used only to discover the frozen robustness shell; all
  stored article links resolve to publisher URLs.

## Opposing approach

The strongest alternative is to delete Claim Trace and submit only an
ambiguity-aware trilingual reader. That product is faster, easier to validate,
and less exposed to retrieval failures. The reason to retain Claim Trace is
that source independence and cross-language claim drift are the project’s most
distinctive technical contribution. It remains optional until independent
evaluation shows that readers understand it.

## Confidence

Medium. The implementation and conservative status rules have strong controlled
coverage, and the main misleading model claim was removed. Confidence cannot be
high until bilingual reviewers, reader sessions, and an Intel machine test are
complete.
