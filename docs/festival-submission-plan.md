# Between the Lines: festival submission plan

Prepared: 24 July 2026  
Target: Intel Vietnam AI Impact Festival, 25 August 2026  
Status: working package; not a claim that evaluation gates have passed

## Official 2026 format

The public organizer page requires:

- a project name of at most 10 words;
- a project description of at most 150 words;
- a two-minute video or vlog;
- the requested signed consent;
- submission through the Google Form by 25 August 2026.

The student category is open to currently enrolled students aged 18 or older,
entering individually or in a team of no more than three. The published rubric
allocates 15 points to impact and inclusion, 20 to AI application and
implementation, and 15 to technical knowledge and skills. The source links and
a line-by-line gap map are in `submission/official-requirements.md`.

## One-sentence pitch

People who read news across English, Vietnamese, and Korean can miss changed
meaning and recycled claims because ordinary translation hides ambiguity and
source relationships; Between the Lines shows the exact wording at risk, then
lets the reader inspect multilingual evidence on an ordinary laptop.

## Demo loop

Use one article with a real ambiguity and one selected factual claim:

```text
article text or public URL
  → translation into the reader's selected language
  → exact phrases whose force, scope, date, number, or attribution may differ
  → reader selects one quoted claim
  → multilingual evidence discovery
  → local passage ranking and duplicate grouping
  → source-bounded status, limitations, links, and reader correction
```

The human chooses the claim and makes the final judgment. The system does not
assign truth scores to articles or trust scores to publishers.

## Evidence already available

### Translation prototype

- 15 full NewJeans articles: five Vietnamese, five English, five Korean.
- A separate 120-URL robustness shell: 40 per language across 12 events and six
  topics; 101/120 pass the current extraction/language/length preflight.
- Six final verification articles produced 116 source segments and 232 target
  segments.
- The original full NLLB shadow pass missed the interactive latency target.
  A risk-routed E5 translation check was fast but did not separate clean from
  deliberately changed controlled translations reliably enough.
- The current quick path makes one selected-target translation call and uses
  deterministic protected-fact checks plus source-grounded model notes. Local
  E5 is reserved for Claim Trace evidence ranking.
- Twelve author passage reviews cover all six translation directions twice.
- The first warning audit judged 12 of 17 meaning-risk prompts useful (70.6%).
  Five false positives were retained as a baseline, fixed, and rerun locally;
  the refined frozen set contains 12/12 useful author-reviewed prompts. This is
  iterative author evidence, not independent precision.
- Six low-stakes general-news smoke articles cover science, education, culture,
  and public events outside entertainment.
- Controlled detector fixture: 18/18 cases. This is regression evidence, not a
  real-world accuracy result.

### Engineering evidence

- The URL-first single-target critical path passes backend, component, type,
  production-build, and eight browser-journey checks.
- Six recent general-news articles produced 21 frozen, source-grounded claim
  candidates across English, Vietnamese, and Korean; all 21 have author review,
  and every article has an acceptable candidate in its top three.
- The 15-article NewJeans corpus produced a complete 67-candidate pool for the
  later benchmark; all 67 have author review and a balanced 30-claim set is
  frozen at ten claims per language.
- The frozen 30-claim runner enforces translation, immutable selection, and
  gold gates; checkpoints batches of at most five; and excludes quota-stopped
  attempts from the result denominator. It has not run because the two-person
  gold evidence adjudication remains open.
- Source excerpts, ratings, retrieval failures, uncertainty, and reader
  corrections remain inspectable.
- Full fetched pages are not retained after excerpt selection.
- Local ranking can switch between PyTorch and OpenVINO.

### Hardware evidence

The frozen M1 development probe ranked the same top five passages with both
runtimes:

- PyTorch median: 1.703 seconds, 17.61 passages/second;
- OpenVINO median: 2.160 seconds, 13.89 passages/second.

Each backend used ten measured runs after warmup and produced identical top-five
rankings. This is an Apple-silicon development result. It does **not** support
an Intel speed, efficiency, or acceleration claim.

## Evidence still required

### Gate A — bilingual translation review

- 12 real-news passage reviews;
- two reviews in every EN/VI/KO direction;
- at least five decided meaning-risk judgments;
- at least 80% of those judgments useful;
- no direction with more negative than positive passage reviews.

Current author-review count: 12 passage reviews and 12 decided meaning-risk
judgments in the refined frozen set. Every direction has two helpful passage
reviews and all 12 current warnings were useful. The gate passes for continued
development, but independent translation validation is still desirable.

### Gate B — factual evidence evaluation

Build 30 adjudicated claims, ten per source language. Report:

| Metric | Gate |
|---|---:|
| Central checkable claim in top three | at least 80% |
| Candidate quote present verbatim | 100% |
| Acceptable evidence in top five | at least 80% |
| Displayed excerpt supports its stated stance | at least 90% |
| Correct status when evidence is sufficient | at least 80% |
| Correct abstention | at least 85% |
| Largest EN/VI/KO gap | at most 10 points |
| Duplicate cluster counted twice | 0 cases |
| One failed page fails the claim | 0 cases |

Record misses and counterexamples, not only aggregate scores.

### Gate C — reader study

Run five to eight sessions. Each reader should:

1. identify what is known from the available evidence;
2. explain why one claim remains unresolved;
3. open the strongest source;
4. distinguish a translation warning from factual evidence.

Measure completion, time, wrong interpretations, and labels that cause
hesitation.

### Gate D — Intel-device benchmark

Use the frozen benchmark workload on a named Intel Core or Core Ultra laptop.
Record:

- exact CPU and RAM;
- OS, Python, PyTorch, OpenVINO, model, precision, and thread settings;
- cold load and warm top-80 ranking latency;
- passages per second and peak resident memory;
- top-k agreement and evidence recall before and after any quantization.

Compare PyTorch with OpenVINO FP32/FP16 first. Test INT8 only if ranking quality
remains within the chosen gate. Keep raw JSON alongside the report.

## Submission assets

Prepare these after the gates:

1. the final 10-word-limit project name and 150-word-limit description;
2. a two-minute video of the complete article-to-human-action loop;
3. a working local demo with one pre-checked fallback case for unreliable
   network access;
4. the signed consent and enrollment information requested in the form;
5. a concise README and reproducible evaluator/benchmark commands;
6. optional architecture, evaluation, responsible-AI, and Intel slides for
   mentoring or later judging—not as assumed first-round requirements.

The signed-in Google Form may contain upload details not visible on the public
page. The entrant must inspect those fields before final rendering.

## Claims language

Safe now:

- “The prototype handles English, Vietnamese, and Korean text.”
- “Optional Claim Trace ranks evidence passages locally with multilingual E5
  on the development laptop.”
- “The evidence path is implemented behind a human-readiness gate.”
- “Controlled tests cover source diversity, abstention, partial failure, and
  feedback.”

Not safe yet:

- “The translator is accurate.”
- “The fact-checker detects misinformation.”
- “The statuses are 80% accurate.”
- “OpenVINO makes it faster.”
- “Intel hardware improves latency or efficiency.”
- “The system is offline.”

Replace each unsafe statement only when a named evaluation, sample size,
hardware record, and raw result support it.

## Execution order

1. Obtain a second qualified adjudicator for the frozen 30-claim evidence key;
   do not represent the author review as independent.
2. Run the fact-checker only after the hash-bound gold validator passes.
3. Review every displayed citation independently and report misses.
4. Run five to eight reader sessions on the frozen interface.
5. Borrow or obtain an Intel laptop and run the frozen hardware benchmark.
6. Assemble the final demo and slides from measured results.

The project should stop or narrow its claim if a gate fails. A clear abstaining
prototype with honest evidence is a stronger festival entry than an expansive
system supported by invented certainty.

Draft submission assets now live in `submission/`. They deliberately retain
`[PENDING]` fields for human, factual-evidence, and Intel-device results.
