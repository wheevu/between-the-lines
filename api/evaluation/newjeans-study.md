# NewJeans multilingual UX and edge-case study

> **Historical architecture:** This study records the earlier two-target
> translation workflow. The current reader path uses one selected-target Gemini
> translation, deterministic protected-fact checks, and grounded notes. NLLB
> and direct E5 translation comparison were removed after latency and
> semantic-validity stress tests.

Date: 2026-07-24  
Machine: MacBook Air M1, 16 GB RAM  
Primary model: Gemini 3.1 Flash-Lite  
Local models: NLLB-200 shadow translation and multilingual E5 similarity  
Languages: English, Vietnamese, and Korean

## Question

Can an everyday reader paste or link a full news article, read useful
translations in the other two languages, notice a small number of meaningful
language risks, recover from common failures, and understand that the warnings
are prompts for review rather than automatic corrections?

This study used 15 full NewJeans articles published within the six months before
24 July 2026: five Vietnamese, five English, and five Korean. Nine discovery
articles were used to expose and fix problems. Six later articles were used for
verification and the human-review queue.

This was an iterative product test, not a blinded model evaluation. The six
verification articles also informed final bounded fixes, so their result is not
an unbiased generalization estimate.

## Corpus and recorded runs

Marker counts for the nine discovery articles are from the first major
refinement pass. Marker counts for the six verification articles are from their
latest final-code run.

| Case | Source | Input | Segments | Seconds | Markers |
|---|---|---:|---:|---:|---:|
| VI-1 | [Yonhap Vietnam](https://vi.yna.co.kr/view/AVI20260427001000880) | URL | 8 | 54.4 | 3 |
| VI-2 | [VOV](https://vov.vn/giai-tri/lieu-minji-co-tro-lai-newjeans-va-nhom-se-khoi-dong-lai-ma-khong-co-danielle-post1289855.vov) | URL | 16 | 62.3 | 2 |
| VI-3 | [Sinh Viên Việt Nam](https://svvn.tienphong.vn/newjeans-bao-gio-moi-thoat-duoc-2-chu-dao-nhac-post1842014.tpo) | URL | 12 | 66.4 | 2 |
| EN-1 | [Seoul Economic Daily](https://en.sedaily.com/news/2026/03/26/ador-and-danielle-clash-over-43-billion-won-damages-in) | URL | 10 | 56.3 | 4 |
| EN-2 | [The Straits Times](https://www.straitstimes.com/life/entertainment/are-k-pop-girl-group-newjeans-returning-as-a-trio-without-minji) | URL | 26 | 120.5 | 4 |
| EN-3 | [Korea JoongAng Daily](https://www.koreajoongangdaily.com/korea/first-hearing-in-adors-lawsuit-against-min-hee-jin-ex-newjeans-member-danielle-to-begin/12578700) | URL | 19 | 80.3 | 5 |
| KO-1 | [Newsis](https://www.newsis.com/view/NISX20260308_0003539403) | URL | 18 | 98.3 | 2 |
| KO-2 | [Insight](https://www.insight.co.kr/news/551730) | URL | 17 | 66.3 | 0 |
| KO-3 | [Newsen](https://www.newsen.com/news_view.php?uid=202605070943050410) | URL | 42 | 200.8 | 2 |
| VI-4 | [Yonhap Vietnam](https://vi.yna.co.kr/view/AVI20260722000500880?section=%2Fhallyu%2Findex) | URL | 15 | 94.6 | 0 |
| VI-5 | [Lao Động](https://laodong.vn/van-hoa-giai-tri/thach-thuc-cua-newjeans-khi-tro-lai-voi-4-thanh-vien-ma-khong-co-danielle-1739349.ldo) | Paste fallback | 28 | 116.6 | 0 |
| EN-4 | [The Korea Times](https://www.koreatimes.co.kr/entertainment/k-pop/20260709/newjeans-sued-for-alleged-copyright-infringement-in-us) | URL | 20 | 112.6 | 0 |
| EN-5 | [Yonhap English](https://en.yna.co.kr/view/AEN20260722001951315) | URL | 19 | 86.5 | 1 |
| KO-4 | [Nate / Dispatch](https://news.nate.com/view/20260708n28577) | URL | 19 | 90.3 | 0 |
| KO-5 | [MBC Entertainment](https://enews.imbc.com/News/RetrieveNewsInfo/512260) | URL | 15 | 86.4 | 2 |

Fourteen articles completed through URL extraction. The Lao Động page rejected
automated extraction, so the provided article text was used through the paste
path. This is a product fallback, not a claim that every publisher URL can be
read automatically.

## Quantitative observations

### Discovery

- The first nine-article run produced 62 markers across 168 source segments and
  336 target-language segments: 18.5 markers per 100 translated segments.
- The first refinement reduced the same discovery set to 24 markers, or 7.1
  per 100 translated segments.
- That reduction came from fixing demonstrable equivalences rather than raising
  one global threshold: locale-formatted numbers, number words and ordinals,
  Korean counting units, compound won amounts, named months, litotes,
  exclusion, termination, and several article boilerplates.

### Final six-article verification

- All six jobs completed, producing 116 source segments and 232 translated
  segments.
- Median full-article time was 92.5 seconds; the range was 86.4–116.6 seconds.
- The median of the 12 target-language similarity medians was 0.929.
- The lowest individual primary-to-shadow similarity was 0.795. Low agreement
  is a review signal, not an accuracy probability.
- Three prompts remained: one meaning-risk and two cultural notes. This is 1.3
  prompts per 100 translated segments.
- Manual inspection judged all three useful, but the sample is tiny and two
  prompts are the same idiom in different target languages. It must not be
  reported as a general 100% precision result.

The controlled 18-pair detector benchmark still passes 18/18 with 1.0 exact
case rate, label precision, and label recall. The full backend suite now has 108
passing tests.

## What the final prompts found

### Omitted ordinal

An English source said Danielle was the “original fifth member.” The Korean
translation called her an original member but omitted “fifth.” The deterministic
number comparison surfaced this as a meaning risk.

### Literal Korean idiom

The Korean phrase `마음을 모았다` was rendered literally as “gathered the
hearts” and `tập hợp tấm lòng`. In this context it means bringing together or
expressing a shared wish. Both target-language results now show a cultural note
with a natural alternative.

### Useful discovery examples

- `퇴출` implies being forced out or expelled. One Vietnamese translation used
  neutral `rời khỏi`; the app suggested `bị loại khỏi`. The English translation
  also neutralized the term but did not surface a note, showing that generated
  note coverage is not symmetric.
- An early user-article run added `4인조 완전체`, roughly “complete
  four-member group,” to a sentence in an article centered on an absent member.
  The new `4` was caught deterministically.

These examples show the intended value: pointing to a specific phrase whose
force, scope, or implication changed. They do not establish factual truth.

## Bugs found and fixed through the article study

### Extraction and segmentation

- HTTP charset metadata caused mojibake on a Korean publisher. Raw bytes are now
  decoded from content.
- Corrupt replacement-character output is rejected with a paste fallback.
- Yonhap related-story headlines after `(END)` were being included as article
  text; extraction now stops there.
- Email lines, alert prefixes, duplicate pasted headings, UI text such as
  “Summarize,” and Korean copyright footers are removed.
- `No. 1` and dotted country abbreviations in legal names are protected during
  sentence splitting. Manual inspection found that `U.S. District Court` had
  been split into three broken fragments even though its job showed no markers.
  The final EN-4 rerun has one complete source sentence and coherent complete
  translations.

### Warning precision

- Number comparison now handles EN/VI/KO number words, ordinals, months,
  weekdays, clock notation, Korean attached counting units, and compound won
  amounts.
- Repeated formatting variants compare as sets, preventing a date written twice
  in one language from looking like a missing fact.
- Paired scope such as “both … and …” is not treated as a literal count.
- Common EN/VI/KO equivalents for absence, contract termination, exclusion, and
  plagiarism no longer generate one-sided polarity warnings.
- Model notes that only restate a factual inconsistency in the source are
  excluded from translation findings. Source-claim verification belongs in the
  later evidence module.
- A common literal form of `마음을 모으다` has a small deterministic check
  because the generative note appeared inconsistently across retries.

### Reliability

- Two iterative runs encountered a transient Gemini 503. Completed jobs were
  retained, input was not cleared, and retrying succeeded. The public error now
  says that Gemini is busy and to retry in a few minutes.
- Analysis links are resumable. Reloading or reopening
  `?analysis=<job-id>` restores a running or completed job.

## UX changes made before and during testing

- The home screen asks for one article and one source language, with URL and
  paste paths instead of a technical dashboard.
- Errors return to the same form with text and URL retained.
- The progress screen uses real stages, a measured 1–3 minute expectation, and
  explains that the tab can be reopened.
- Results show one target language at a time as continuous readable paragraphs.
- The original is optional and appears beside the translation on wide screens
  or above it on mobile.
- The full translation copies with paragraph breaks intact.
- Findings are separated from the article, linked back to the sentence, capped
  at four initially, and described as passages worth checking rather than
  automatic corrections.
- Target-language passage feedback asks whether the translation was useful and
  accepts an unflagged missed issue.
- Desktop, 390-pixel mobile, long-result, zero-finding, and finding states were
  visually checked.

## Remaining limitations

- Gemini receives the source article. NLLB and E5 are local, so the prototype is
  partly local rather than offline.
- Gemini notes are stochastic. The deterministic rules cover a small set of
  high-value language patterns, not general linguistic understanding.
- Number comparison uses sets. It can miss the loss of one occurrence when the
  same exact number appears multiple times in a sentence.
- E5 similarity and the back-translation thresholds are heuristics, not
  calibrated confidence scores.
- A paste fallback currently loses the publisher title and source link in the
  result header.
- The study stayed within entertainment reporting about one group. It does not
  establish behavior on medicine, politics, finance, or other high-stakes news.
- Human bilingual passage reviews have not yet been collected. The study author
  manually inspected surfaced and selected unsurfaced cases, but this is not a
  substitute for independent readers.
- No claim has been fact-checked. The app checks translation differences only.

## Human review queue

Run the backend and frontend, then open these resumable results. Review both
language tabs for every article, including results with no findings.

### Vietnamese sources

1. [VI-4 Yonhap result](http://127.0.0.1:5173/?analysis=ab7bcad4-0742-40de-8df6-a785671e22bc)
2. [VI-5 user-provided Lao Động result](http://127.0.0.1:5173/?analysis=fd18d5e6-4a64-4827-a7bb-0042e8ec4d3c)

### English sources

3. [EN-4 Korea Times result](http://127.0.0.1:5173/?analysis=85f52083-84e1-4adf-945f-8484c4f16664)
4. [EN-5 Yonhap result](http://127.0.0.1:5173/?analysis=93f42ef1-3449-4ce5-ae74-281ea354d9d6)

### Korean sources

5. [KO-4 Nate / Dispatch result](http://127.0.0.1:5173/?analysis=bce7bf4e-2420-4b52-92f2-6a7bb9a29a1c)
6. [KO-5 MBC result](http://127.0.0.1:5173/?analysis=137c8041-7cc7-4f1a-9914-473159b7e0f7)

This queue gives two passage reviews for every translation direction. It has
only one meaning-risk marker because false-positive reduction worked. Continue
reviewing naturally flagged articles until at least five decided meaning-risk
judgments exist.

## Decision

The prototype is ready for independent translation UX review. It is **not yet
ready to claim validated warning usefulness or to merge automated factual
conclusions into the reader UI**.

Advance from planning to an integrated evidence module only when feedback shows:

1. two passage reviews for all six language directions;
2. at least five decided meaning-risk judgments;
3. at least 80% of decided meaning-risk judgments are useful;
4. no direction has more negative than positive passage reviews;
5. reviewers can explain that translation findings and factual evidence are
   different layers.

The proposed next layer is documented in
[`docs/fact-check-module-plan.md`](../../docs/fact-check-module-plan.md).
