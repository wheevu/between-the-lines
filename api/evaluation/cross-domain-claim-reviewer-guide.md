# General-news claim-candidate reviewer guide

This review asks whether Between the Lines proposes faithful, useful claims
before any source search occurs. It does not ask whether the article’s claim is
true.

## Materials

- `cross-domain-claim-candidates.json` is the frozen model output.
- `cross-domain-claim-review.csv` is the sheet to complete.
- Every row includes the public source URL, exact article quote, standalone
  claim, candidate rank, and proposed type.

Use a strong reader for the row’s source language. Prefer independent reviewers;
mark self-review as `author` rather than presenting it as independent.

## Three judgments

Enter `yes`, `no`, or `unsure` in each column.

### Faithful

Choose **yes** only when the standalone claim preserves the selected quote’s:

- speaker or source;
- negation and uncertainty;
- future plan versus completed event;
- names and referents;
- dates, quantities, units, comparisons, and scope.

It may remove incidental wording, but it must not turn an allegation into an
event, infer an unstated total, or make a claim more certain.

### Central and checkable

Choose **yes** when the claim matters to the article’s main subject and a reader
could reasonably compare it with public evidence.

Choose **no** for trivia, promotional language, private mental states, vague
quality judgments, or details whose only possible source is the same article.

### Type correct

- `fact`: a concrete assertion about an event, record, measurement, or published
  result.
- `attributed`: verifies that a named person or organization made a statement,
  allegation, interpretation, forecast, plan, or schedule. It does not establish
  the statement’s inner allegation.
- `unsuitable`: opinion, prediction without a checkable attribution, rhetorical
  question, vague judgment, or private state.

Choose **yes** only when the proposed type matches these meanings.

## Notes and identity

- Use a pseudonymous `reviewer_id`; do not put an email address in the sheet.
- Use `independent` or `author` for `reviewer_role`.
- Explain every **no** briefly in `notes`, especially added/dropped wording or a
  better claim from the article.
- Use **unsure** when language knowledge is insufficient. Do not guess to finish
  the sheet.

## Summary

From `api/`:

```sh
.venv/bin/python scripts/summarize_claim_review.py
```

The summary reports a top-three success for an article only after its first
three candidates have judgments and at least one receives **yes** on all three
dimensions. Blank and unsure rows do not become passes.

This six-article set is a cross-domain smoke evaluation. It can expose obvious
language or topic failures, but it does not replace the later 30-claim
adjudicated factual-evidence set.
