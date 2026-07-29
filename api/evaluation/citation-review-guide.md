# Citation review guide

This review measures whether the passages cited by the frozen system assessment
actually deserve their role. It is separate from the gold-status adjudication:
the reviewer may inspect the frozen claim and system citation, but should not
copy or consult the answer key.

## Prepare the sheet

Run the automatic scorer first:

```sh
.venv/bin/python scripts/summarize_system_evaluation.py
```

Continue only when it reports `ready_for_human_citation_review: true`, then run:

```sh
.venv/bin/python scripts/prepare_citation_review.py
```

The generated CSV is hash-bound to `newjeans-system-results.json`. Do not edit
the claim, rank, URL, excerpt, stance, or citation-role columns. If the system
run changes, move the old review beside that run and generate a new sheet.

## Review each row

Use `yes`, `no`, or `unsure` for all three judgments:

- `relevant_to_claim`: the passage addresses the same person, event, date, and
  scope as the frozen claim;
- `excerpt_matches_source`: the quoted words appear on the linked page and are
  not made misleading by omitted nearby context;
- `stance_correct`: the passage genuinely supports, disputes, or supplies
  context in the role recorded by the system.

Open the source rather than judging from the URL or publisher name. Use
`unsure` when a page is unavailable, a language cannot be read confidently, or
the relationship cannot be decided. Record the reason in `notes`; do not turn
uncertainty into a convenient yes.

Record a pseudonymous reviewer ID and the honest reviewer role. The festival
gate requires independent review. Different independent reviewers may cover
different evidence languages if one person cannot confidently read all three.

The sheet contains only evidence IDs referenced by the final assessment.
Retrieved passages listed by the interface as “other sources reviewed” are not
citations and are excluded from this citation-correctness denominator.

## Summarize

```sh
.venv/bin/python scripts/summarize_citation_review.py
```

`ready_for_reporting` means the sheet is structurally complete and unchanged.
It is not a quality pass. `citation_gate_passed` additionally requires:

- at least one citation;
- every row reviewed independently;
- no `unsure` judgment;
- at least 90% of citations receiving yes on all three judgments.

The summary reports the denominator, counterexamples, and source-language
breakdown. A row with one no or unsure judgment is not counted as correct.
