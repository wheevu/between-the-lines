# Evaluation

The translation studies below preserve earlier two-target and local-comparator
experiments. They are historical evaluation artifacts, not the current reader
architecture. The live fast path makes one selected-target Gemini call, then
runs deterministic protected-fact checks and displays grounded notes; NLLB and
direct E5 translation comparison were removed after stress testing.

`cases.jsonl` is a controlled detector benchmark: three hand-checked translation
pairs for each of the six English, Vietnamese, and Korean directions. It covers
clean pairs, deterministic number/negation changes, meaning-risk notes, and
cultural notes.

Run it from `api/`:

```sh
.venv/bin/python scripts/evaluate_detector.py
```

This benchmark tests whether known signals become the right review labels. It
does not measure translation quality or prove that a generated warning is useful
to a reader. Follow the [six-passage reviewer guide](reviewer-guide.md) with at
least one strong Korean–English reader. Judge every surfaced note and both target
translations, including important issues the app missed.

Portable translation-review artifacts:

- `translation-feedback.csv` contains the exported passage and flag judgments,
  including the retained pre-refinement false positives.
- `translation-readiness-summary.json` is the scoped current-set gate result.
- `translation-refinement-2026-07-24.json` maps the original analyses to the
  local detector-refinement rerun.

The [15-article NewJeans study](newjeans-study.md) records the current
full-article UX, extraction and edge-case work.

The newer [Claim Trace multi-topic study](claim-trace-study.md) expands testing
to 36 real articles, 12 per language, across six news domains. Its frozen
manifest, live extraction report, balanced six-topic closed-set pilot, and M1
shadow-decoding comparison are:

- `claim-trace-corpus.json`
- `claim-trace-preflight-2026-07-24.json`
- `claim-trace-closed-set-pilot.json`
- `shadow-decoding-m1.json`

Run the non-generative ingestion preflight:

```sh
.venv/bin/python scripts/run_claim_trace_preflight.py
```

Run the six-case source-known alignment and lineage pilot:

```sh
.venv/bin/python scripts/run_claim_trace_closed_set.py --limit 6
```

The pilot intentionally excludes discovery so a search-provider outage cannot
be mistaken for an alignment or source-independence result. It is a development
test, not an independent accuracy measurement.

Run the frozen 24-case suite and the 12-article local-stage benchmark:

```sh
.venv/bin/python scripts/run_claim_trace_closed_set.py --suite full
.venv/bin/python scripts/benchmark_selective_embeddings.py --limit 12 --runs 5
```

Validate and reproduce the answerability-adjusted recall audit:

```sh
.venv/bin/python scripts/validate_recall_oracle.py
.venv/bin/python scripts/run_recall_diagnostics.py --output /tmp/recall-check.json
.venv/bin/python scripts/validate_publisher_holdout.py
.venv/bin/python scripts/run_publisher_holdout.py --output /tmp/holdout-check.json
```

The author-reviewed oracle finds 18 answerable and six unanswerable cases. A
retrospective diagnostic preserves already-identified anchors through ranking
in 18/18 cases; this is localization, not unbiased recall. The separately
pre-frozen publisher-held-out set reaches 10/12 at ranking@6. See
`claim-trace-recall-report-2026-07-26.md` for the stage-level interpretation and
limitations. Do not present these author labels as independent accuracy.

The stress-test rules and current baseline are in
`stress-test-scorecard-v1.json` and `stress-test-baseline-2026-07-25.md`.
`selective-verification-m1.json` records why NLLB shadow translation was removed
from the interactive path; it remains an offline comparison, not a product
latency claim.

The [implementation review](fact-check-implementation-review.md) records what
has been verified, what remains untested, and why no factual-quality or Intel
performance claim is currently allowed.

Generate the frozen general-news claim candidates while Gemini quota is
available:

```sh
.venv/bin/python scripts/generate_cross_domain_claims.py
```

The resulting `cross-domain-claim-candidates.json` stores exact quotes,
candidate metadata, source hashes, and generation metadata, but not full article
text or truth labels. It is input to human centrality/checkability review, not
evidence that claim selection is accurate.

Prepare and summarize the bilingual claim review:

```sh
.venv/bin/python scripts/prepare_claim_review.py
# Fill faithful, central_checkable, and type_correct with yes, no, or unsure.
.venv/bin/python scripts/summarize_claim_review.py
```

Record a pseudonymous reviewer ID and `author` or `independent` role. The summary leaves
incomplete cases undecided and never treats blank cells as successful reviews.
Use the [claim reviewer guide](cross-domain-claim-reviewer-guide.md) for the
three judgment definitions.

## Thirty-claim pool

The 15-article NewJeans corpus is machine-readable in
`newjeans-corpus.json`. Generate its source-grounded pool with:

```sh
.venv/bin/python scripts/generate_newjeans_claim_pool.py
```

The script reuses completed cases with the same model, manifest, and source
hash. If free-tier quota stops a run, it writes an explicitly incomplete pool
and resumes without spending another model call on completed cases. The pool is
only input to human selection of ten claims per source language; it contains no
truth, evidence, or status labels.

Prepare and validate the 30-claim selection:

```sh
.venv/bin/python scripts/prepare_newjeans_claim_selection.py
# Complete evaluation/newjeans-claim-selection.csv.
.venv/bin/python scripts/summarize_newjeans_claim_selection.py
```

Use the [30-claim selection guide](newjeans-claim-selection-guide.md). The
structural gate requires all 67 candidates to be reviewed, exactly ten selected
per language, all 15 articles represented, and exactly two claims per language
in each of the five evaluation categories.

After the selection summary passes, prepare the independent gold-evidence
adjudication:

```sh
.venv/bin/python scripts/prepare_evidence_adjudication.py
# Two independent reviewers complete evaluation/newjeans-evidence-adjudication.json.
.venv/bin/python scripts/validate_evidence_adjudication.py
```

Use the [evidence adjudication guide](evidence-adjudication-guide.md). The
validator ties the gold file to the exact selection sheet and requires all 30
claims, ten per language, two distinct pseudonymous reviewers explicitly
labeled `independent`, a timezone-aware check date, rationale,
publication-dated exact evidence excerpts, and independent publishers and hosts
for resolved stances. An `insufficient` label must record the search scope. The
author and the system's own results must never be counted as independent gold
reviewers.

## Author/AI-assisted evidence pilot

The separate `newjeans-author-evidence-pilot.json` lets the project author
exercise the evidence-review method before independent reviewers are available:

```sh
.venv/bin/python scripts/validate_author_evidence_pilot.py
```

The pilot is bound to the same frozen selection and requires 30 complete
reviews, ten per language, exact dated excerpts, and two publishers and hosts
for every resolved stance. It currently contains 25 `supported`, three `mixed`,
one `disputed`, and one `insufficient` exploratory labels.

This file is deliberately incompatible with the independent gold validator and
system-evaluation runner. Its summary always reports
`independent_gold_ready: false`. Use it to refine claim wording, evidence-search
rules, and reviewer guidance—not to calculate accuracy or unlock the production
fact-check UI. See the [pilot findings](author-evidence-pilot.md).

After the frozen system run, calculate automatic metrics and create the
independent citation review:

```sh
.venv/bin/python scripts/run_system_evaluation.py --limit 3
# Repeat after checking free quota until the checkpoint reports complete.
.venv/bin/python scripts/summarize_system_evaluation.py
.venv/bin/python scripts/prepare_citation_review.py
# Complete evaluation/newjeans-citation-review.csv without editing frozen fields.
.venv/bin/python scripts/summarize_citation_review.py
```

Use the [citation review guide](citation-review-guide.md). The sheet contains
only passages that the final assessment actually cites. The summary checks the
system-run hash and every immutable citation field, reports counterexamples and
per-language rates, and applies the ≥90% gate only after every citation has a
decided independent review.

The system runner enforces the translation, selection, and gold gates before
network use. It writes an atomic, resumable artifact and stops rather than
turning a Gemini quota failure into an `insufficient` evaluation label. The
required `--limit` accepts one to five new claims per invocation. This limits
accidental quota use; it cannot determine whether the configured Google account
has billing enabled, so confirm free-tier availability before each batch.

Advance to evidence cross-checking only after:

- at least 80% of meaning-risk notes are judged useful;
- no systematic EN, VI, or KO direction fails;
- reviewers can explain the difference between a meaning risk and a cultural
  note;
- median processing time is acceptable on the target laptop.
