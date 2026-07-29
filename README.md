# Between the Lines

An ambiguity-aware English, Vietnamese, and Korean news reader. Paste an
article or supply a public URL, choose the language you want to read, and the
app produces one aligned translation with inspectable language notes and
protected-fact checks.

The prototype includes a reviewer-gated Claim Trace workflow. It identifies source-grounded claims,
lets the reader choose one, searches in all three languages, ranks excerpts
locally, aligns literal passages, groups reporting that credits the same origin,
and shows provenance, wording differences, limitations, partial failures, and
reader feedback. The workflow is available for prototype testing through an
explicit `?reviewer=author` or `?reviewer=independent` URL. It remains hidden in
the ordinary reader flow until the independent factual and reader gates pass,
and it is not presented as validated factual accuracy.

## How it works

1. Gemini 3.1 Flash-Lite produces a sentence-aligned translation in the
   reader-selected language and grounded translation notes.
2. Deterministic checks protect numbers and negation. Model-supplied notes are
   shown only when their quoted spans exist in the source and translation.
3. Results, cached analyses, and reviewer feedback stay in local SQLite.
4. Optional Claim Trace discovers URLs through Google Search grounding and
   the optional Fact Check Tools API, fetches bounded excerpts, and ranks them
   with multilingual E5. E5 also conservatively helps group differently
   written credited-origin names so translated wire reports do not count as
   independent sources. Full fetched pages are not persisted.

The source article and selected evidence excerpts are sent to Gemini. E5
evidence ranking, analysis results, and feedback stay on this Mac. NLLB is
retained only in offline evaluation scripts that document a rejected
translation-comparison design; it does not run in the reader workflow.

## Run locally

Backend, from the project root:

```sh
cd api
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

The backend reads `GOOGLE_GENERATIVE_AI_API_KEY` from the environment. It does
not need to be placed in a project file.

`GOOGLE_FACT_CHECK_API_KEY` is optional. Without it, professional fact-check
lookup is skipped. The open-web evidence path still depends on available Gemini
Google Search grounding quota.

PyTorch remains the default local embedding runtime. The optional OpenVINO
development path is documented in
`api/evaluation/embedding-benchmark-m1.md`; it must not be presented as an
Intel speed result until the same workload is measured on Intel hardware.

Frontend, in another terminal:

```sh
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Translation does not download a local model. The
first Claim Trace run that reaches local evidence ranking downloads
multilingual E5 to the Hugging Face cache.

## Verify

```sh
cd api
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python scripts/evaluate_detector.py
.venv/bin/python scripts/summarize_feedback.py
.venv/bin/python scripts/export_fact_check_feedback.py > fact-check-feedback.csv

cd ../web
npm run check
npm run test
npm run test:e2e
npm run build
```

See the [36-article Claim Trace study](api/evaluation/claim-trace-study.md),
[15-article UX study](api/evaluation/newjeans-study.md),
[six-passage reviewer guide](api/evaluation/reviewer-guide.md), and
[fact-check module plan](docs/fact-check-module-plan.md). The current
[implementation review](api/evaluation/fact-check-implementation-review.md)
separates verified behavior from pending live evaluation, and the
[festival submission plan](docs/festival-submission-plan.md) lists the evidence
still required before August submission. Working evaluation, responsible-AI,
architecture, demo, and slide drafts are collected in
[`submission/`](submission/README.md).
