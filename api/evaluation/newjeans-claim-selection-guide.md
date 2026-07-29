# Thirty-claim selection guide

The 67-row pool comes from the 15 NewJeans articles in the multilingual UX
study. This step selects a balanced 30-claim benchmark; it does not assign truth
statuses or acceptable evidence yet.

## Review every candidate

For each row in `newjeans-claim-selection.csv`, judge:

- `faithful`: the standalone claim preserves the visible quote’s attribution,
  negation, uncertainty, time, number, unit, and scope;
- `central_checkable`: the claim matters to the article and can be compared with
  public evidence;
- `type_correct`: `fact` or `attributed` has the meaning described in the
  general-news claim reviewer guide;
- `include_in_30`: select only a claim with **yes** on all three earlier
  judgments.

Use `yes`, `no`, or `unsure`. Explain every rejected or unsure high-ranked
candidate in `notes`.

Use a pseudonymous reviewer ID and mark the role `author` or `independent`.
Strong readers should review their source language. Do not turn machine
translation into a Korean-language gold label.

## Selection balance

Select exactly ten claims per source language and at least one claim from every
article. Within each language, select exactly two claims in each primary
category:

- `number`: a quantity, percentage, money amount, count, rank, or measurable
  comparison is central;
- `date`: timing, sequence, duration, or change over time is central;
- `legal-attribution`: lawsuit, ruling, contract, allegation, or quoted legal
  position where attribution must not become proof;
- `direct-announcement`: a checkable release, schedule, return, publication, or
  official organizational statement;
- `abstention`: deliberately likely to lack two independent public evidence
  clusters, contain a compound scope mismatch, or require the system to remain
  unresolved.

`primary_category` records the main test purpose even when a claim fits more
than one.

Do not choose a weaker claim merely to fill a category. If the pool cannot meet
the balance with faithful central claims, record that as a corpus failure and
revise the corpus before retrieval—not the labels afterward.

## Structural summary

From `api/`:

```sh
.venv/bin/python scripts/summarize_newjeans_claim_selection.py
```

The selection becomes structurally ready only when:

- all 67 pool candidates have complete judgments and reviewer identity;
- all selected rows have three **yes** judgments;
- each language has exactly ten selected claims;
- every language has exactly two claims in every category;
- all 15 source articles are represented.

The summary also compares every case, language, publisher, source URL, rank,
claim type, quote, and standalone claim with the frozen pool. If a spreadsheet
rewrites one of those fields, restore the row from the pool instead of
adjudicating the edited text.

After this passes, freeze the CSV and create the separate evidence-adjudication
sheet. Do not change selected claims in response to system retrieval results.
