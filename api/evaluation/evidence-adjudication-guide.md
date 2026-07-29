# Evidence adjudication guide

This review creates the independent answer key for the frozen 30-claim set. It
does not grade the prose quality of Between the Lines and must not use the
system's own retrieval result as evidence.

## Before starting

- Run `scripts/summarize_newjeans_claim_selection.py`. Do not continue unless
  `ready_for_evidence_adjudication` is `true`.
- Run `scripts/prepare_evidence_adjudication.py` once.
- Use two independent reviewers with the language and topic knowledge needed
  for the claim. Record pseudonymous IDs and the role `independent`; do not use
  the project author or system output to satisfy this requirement:

  ```json
  "adjudicators": [
    {"id": "reviewer-a", "role": "independent"},
    {"id": "reviewer-b", "role": "independent"}
  ]
  ```
- Search independently in a normal browser. Keep the claim's check date fixed
  because news evidence can change.

## Gold fields

Choose one `expected_status`:

- `supported`: the central claim is supported by adequate independent evidence.
- `disputed`: adequate independent evidence contradicts the central claim.
- `mixed`: material parts are both supported and disputed.
- `insufficient`: the search did not find enough independent evidence to
  resolve the claim.

For each acceptable evidence set, record:

- the source URL and publisher;
- the source language (`en`, `vi`, or `ko`);
- its stance (`supports`, `disputes`, or `context`);
- an exact, short excerpt that contains the relevant evidence;
- the source's ISO publication date;
- why the publishers are independent rather than copies of one report.

For `supported` or `disputed`, one acceptable set needs at least two distinct
publishers on two distinct hosts for the relevant stance. A `mixed` set needs
that minimum for both supporting and disputing evidence. Multiple acceptable
sets are allowed when different combinations independently justify the same
status.

For `insufficient`, leave acceptable sets empty unless a partial-context set is
useful, and explain in `search_notes` which queries, languages, date range, and
source types were checked. Absence of a quick search result is not evidence of
falsehood.

## Resolution rules

- Judge the frozen standalone claim, while consulting its exact source quote.
- Separate the publisher's attribution from the truth of the attributed
  statement.
- Treat syndicated copies and articles repeating one original report as one
  evidence lineage.
- Prefer primary records for legal rulings, company announcements, and exact
  dates or numbers. Secondary coverage may help explain context.
- If reviewers disagree, discuss the evidence and record the final rationale.
  Preserve unresolved disagreement in `adjudication_notes`.
- Do not change the selected claim text. If a claim is unsafe or malformed,
  return to the selection sheet and regenerate the adjudication file; its hash
  must change.

Run `scripts/validate_evidence_adjudication.py` after every review session. A
passing structural check means the answer key is complete enough to evaluate;
it does not itself prove that an excerpt is accurate or that two sources are
truly independent.

After the frozen 30-claim output is stored as
`newjeans-system-results.json`, run:

```sh
.venv/bin/python scripts/summarize_system_evaluation.py
```

Create that output only through the gated runner:

```sh
# First confirm the configured Gemini account still has free quota.
.venv/bin/python scripts/run_system_evaluation.py --limit 3
# Repeat later; completed claims are reused from the atomic checkpoint.
```

The runner refuses to start until translation readiness, the immutable balanced
selection, and independent gold adjudication all pass. It binds the output to
the corpus, pool, selection, adjudication, model, embedding backend, and
fact-check pipeline hash. A quota-exhausted attempt is recorded but is not
accepted as an evaluated claim. Each invocation is capped at five new claims,
and a complete artifact cannot be overwritten.

The code has no paid fallback and stores no credentials, but it cannot inspect
the billing state of a Google account. Confirm free-tier quota outside the app
before every batch. Do not run two evaluation commands concurrently.

The scorer hash-binds the run to this adjudication, requires the exact claim
text and IDs, reports retrieval-at-five and status metrics by language, and
checks that resolved statuses still obey publisher and duplicate-cluster
independence. A matching URL counts only as retrieval. The scorer deliberately
reports zero citation judgments until people review whether each displayed
excerpt supports its stated stance.

When it reports `ready_for_human_citation_review: true`, prepare the separate
hash-bound review sheet:

```sh
.venv/bin/python scripts/prepare_citation_review.py
# An independent reviewer completes evaluation/newjeans-citation-review.csv.
.venv/bin/python scripts/summarize_citation_review.py
```

Follow the [citation review guide](citation-review-guide.md). The citation gate
cannot pass on blank, unsure, author-only, missing, duplicated, or altered rows.
