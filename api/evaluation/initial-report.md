# Initial prototype evaluation

> **Historical architecture:** This report records an earlier prototype. The
> current reader path uses one selected-target Gemini translation,
> deterministic protected-fact checks, and grounded notes. NLLB and direct E5
> translation comparison were removed after latency and semantic-validity
> stress tests.
>
> Superseded for full-article UX conclusions by the
> [15-article NewJeans study](newjeans-study.md). This document preserves the
> earlier smoke-test record.

Date: 2026-07-24  
Machine: MacBook Air M1, 16 GB RAM

## What passed

- All six live translation directions completed with Gemini 2.5 Flash as the
  primary translator, local NLLB-200 as the shadow translator, and multilingual
  E5 similarity scoring.
- The three one-sentence source jobs completed in 28.6 seconds (EN), 8.9 seconds
  (VI), and 27.6 seconds (KO). The first includes local model loading.
- Primary-to-shadow similarity ranged from 0.906 to 0.957 across the six outputs.
- The controlled detector benchmark matched all expected labels on 18/18 pairs:
  100% exact-case rate, label precision, and label recall.
- The browser journey passed article entry, progress polling, three-column review,
  note filtering, and feedback submission.
- The first live run exposed a false number warning when “September” became
  “tháng 9 / 9월.” A month-aware regression test now covers that case.
- A user-provided 764-word Vietnamese entertainment article completed in 137
  seconds after cleanup, producing 28 segments and both English and Korean
  translations. Median primary-to-shadow similarity was 0.939 for English and
  0.917 for Korean.
- That article exposed seven false warnings involving locale-formatted numbers,
  Korean counting units, Vietnamese litotes, exclusion, and question polarity.
  Focused EN/VI/KO regressions now cover those cases.
- On the corrected rerun, the detector found one substantive Korean addition:
  “appeared as a group” became `4인조 완전체` (“complete four-member group”).
  The extra `4` was caught deterministically; “complete group” is also
  potentially misleading in an article centered on an absent member. One
  separate Gemini lexical note was accurate but not especially useful.

The default primary model is now Gemini 3.1 Flash-Lite. The earlier six-direction
smoke test used Gemini 2.5 Flash; the 3.1 model was live-tested on the full
Vietnamese-to-English and Vietnamese-to-Korean article paths after the 2.5 free
quota was exhausted.

## What this does not prove

The 18-pair benchmark is deliberately constructed and tests known detector
behavior. The long-form user test covers one entertainment article and two of
the six translation directions. These results do not establish warning
usefulness, translation quality across news domains, or threshold calibration.

Adversarial review also identified two limits to carry into testing: the
similarity thresholds are heuristics rather than calibrated probabilities, and
the deterministic number checker is not yet a general date/currency parser.
Article text is serialized as untrusted JSON data in the Gemini prompt, but
model-level prompt injection remains a test case rather than a solved problem.

Gemini still receives source text, so the product is not fully offline. NLLB and
E5 stay local. NLLB-200’s model license is suitable for this research prototype
but must be revisited before commercial use.

## Human test gate

Before adding source retrieval or fact-checking:

1. Follow the [current six-passage reviewer guide](reviewer-guide.md) across EN, VI,
   and KO.
2. Have a strong Korean–English reader label every note Yes, No, or Unsure and
   review each target translation, including important missed issues.
3. Export feedback with `.venv/bin/python scripts/export_feedback.py`.
4. Run `.venv/bin/python scripts/summarize_feedback.py`.
5. Continue only when the summary reports that the dataset is ready for the
   evidence-layer decision.
