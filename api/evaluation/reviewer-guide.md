# Human reviewer guide

Use the six completed NewJeans analyses below: two Vietnamese, two English, and
two Korean. Reviewing both target tabs gives two observations for each of the
six translation directions.

Start the backend and frontend before opening the local links.

## Review set

### Vietnamese source

1. [Yonhap — four-member return](http://127.0.0.1:5173/?analysis=ab7bcad4-0742-40de-8df6-a785671e22bc&reviewer=independent)
2. [Lao Động — challenges without Danielle](http://127.0.0.1:5173/?analysis=fd18d5e6-4a64-4827-a7bb-0042e8ec4d3c&reviewer=independent)

### English source

3. [The Korea Times — U.S. copyright suit](http://127.0.0.1:5173/?analysis=85f52083-84e1-4adf-945f-8484c4f16664&reviewer=independent)
4. [Yonhap — four-member return](http://127.0.0.1:5173/?analysis=93f42ef1-3449-4ce5-ae74-281ea354d9d6&reviewer=independent)

### Korean source

5. [Nate / Dispatch — `ETA` copyright suit](http://127.0.0.1:5173/?analysis=bce7bf4e-2420-4b52-92f2-6a7bb9a29a1c&reviewer=author)
6. [MBC — four-member anniversary content](http://127.0.0.1:5173/?analysis=137c8041-7cc7-4f1a-9914-473159b7e0f7&reviewer=author)

The `reviewer` value is stored with every judgment. The Korean links are
deliberately marked `author`; this makes the self-review visible rather than
presenting it as independent validation. Change the other links to
`reviewer=author` if the project author reviews them too.

## One review

1. Read the full first target-language translation before opening the original.
2. Turn on **Show original** and check names, numbers, attribution, negation,
   legal language, and any wording that feels unusually literal.
3. Mark every surfaced finding Yes, No, or Unsure. A result with no findings
   still needs a full passage review.
4. At the bottom, answer whether that target translation was useful. If not,
   point to the most important changed or missing phrase.
5. Save the review, switch language tabs, and repeat.

Use **Yes** when a finding correctly points to wording worth checking, **No**
when it is noise or misleading, and **Unsure** when you cannot judge the
language pair confidently. A strong Korean–English reader should judge the
Korean–English directions.

## Read the results

After all six passages:

```sh
cd api
.venv/bin/python scripts/export_feedback.py --output evaluation/translation-feedback.csv
.venv/bin/python scripts/summarize_feedback.py \
  --output evaluation/translation-readiness-summary.json
```

The six-article queue contains one meaning-risk finding after precision cleanup.
The frozen authored risk extension supplies the remaining naturally surfaced
warning judgments. Do not add noise just to increase the count.

The continuation gate requires:

- 12 passage reviews;
- two reviews in every language direction;
- at least five decided meaning-risk judgments;
- at least 80% meaning-risk usefulness;
- no direction with more negative than positive passage reviews.

The full methodology and known limitations are in the
[NewJeans study](newjeans-study.md).

## Meaning-risk extension set

The six news articles surfaced too few meaning-risk prompts to test usefulness
without reintroducing detector noise. Three clearly labeled synthetic passages
were therefore authored with attribution, negation, modality, dates, numbers,
conditions, and idioms. They are evaluation material, not reports of real
events.

They produced 16 meaning-risk prompts:

1. [English source — transit trial](http://127.0.0.1:5173/?analysis=86eeed07-6728-4766-979e-3b05a1f37e30&reviewer=independent)
   — 2 meaning risks
2. [Vietnamese source — library opening](http://127.0.0.1:5173/?analysis=06bb6f4c-43f7-4ac5-98f9-3d7db7392c4b&reviewer=independent)
   — 8 meaning risks
3. [Korean source — garden program](http://127.0.0.1:5173/?analysis=3cd49e1d-03e4-4902-bfa4-960d9c14a81a&reviewer=author)
   — 6 meaning risks

Judge at least five meaning-risk prompts across more than one target language.
The Korean link is marked as author review. The English and Vietnamese links
are prepared for an independent reviewer; if the author opens either, change
the query value to `reviewer=author` before saving feedback.

The synthetic passages do not count toward the 12 real-news passage reviews.
Their overall passage answers may be saved, but the readiness script excludes
them from news coverage and uses only their individual meaning-risk judgments.
