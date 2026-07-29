# Gated fact-check implementation review

Date: 24 July 2026  
State: implemented behind the translation-readiness gate

## What is built

The dormant workflow now covers:

1. exact-quote claim extraction from stored source segments;
2. explicit selection of one claim, with no preselection;
3. two search queries in each of English, Vietnamese, and Korean;
4. professional fact-check discovery when an optional API key is available;
5. Google Search grounding URL discovery using grounding metadata only;
6. bounded page extraction with self-citation, private-network, duplicate,
   publisher, page, and download limits;
7. local multilingual E5 passage ranking with publisher and syndication
   diversity;
8. structured evidence stance comparison;
9. deterministic supported, disputed, mixed, or insufficient status rules;
10. resumable progress and results, partial source failures, provenance,
    limitations, publisher ratings, and reader feedback.

Full fetched pages are transient. The database stores the selected excerpt,
canonical URL, publisher key, language, retrieval time, relevance, stance,
cluster, and content hash.

## What the tests establish

- 186 backend tests pass.
- 12 component tests pass.
- Six browser journeys pass, including a keyboard focus path, a running
  fact-check resumed from its URL, and evidence feedback tied to the correct
  excerpt.
- Type checking, Python lint, and the production web build pass.
- A failed page does not fail the retrieval batch.
- Invented evidence feedback targets are rejected.
- A repeated syndication cluster cannot count twice.
- Two articles from one publisher cannot satisfy the independence rule.
- A model-classified primary excerpt cannot bypass that rule alone.
- Multi-claim progress does not move backward.

These are controlled implementation checks. They do not establish that real
search results contain the best evidence or that statuses are correct.

## Live status

The refined readiness summary currently reports:

- 12 of 12 required real-news passage reviews;
- two helpful author passage reviews in every language direction;
- 12 decided current meaning-risk judgments, all marked useful by the author.

The initial warning audit scored 12/17 (70.6%). Four ordinal false positives and
one redundant conditional warning were fixed, then the stored translations and
grounded notes were rerun locally without another model call. The original
negative judgments remain available. The continuation gate now passes, while
independent translation validation remains outstanding.

A live Gemini Google Search grounding probe reached the query stage but returned
HTTP 429 because the available free quota was exhausted. Grounding-metadata
parsing is covered by a controlled test, but a live source set has not been
validated. No Fact Check Tools key is configured. Provider outage behavior is
tested and returns an insufficient result with an explicit limitation rather
than invented evidence.

## Adversarial review

### Blockers found and fixed

- **False independence:** status logic originally counted two duplicate
  clusters without also requiring two publishers. It now requires both.
- **Model bypass:** one excerpt labeled primary/direct by Gemini could
  originally satisfy the status rule. Because that label is not authenticated,
  the prototype now requires two independent publishers and clusters.
- **Backward progress:** fixed ranking and synthesis percentages caused a second
  claim to restart below the first claim’s percentage. Progress is now allocated
  monotonically across selected claims.
- **Lost provenance:** publisher ratings and retrieval times were discovered but
  not retained in ranked evidence. They now survive persistence and appear in
  the reader UI.

### Remaining risks

- Search query validation deterministically protects numeric anchors, but names
  and dates written without digits still require human evaluation.
- Source-type and stance reasons are model judgments. They are displayed beside
  the exact excerpt, cannot alone satisfy independence, and can be reported by
  readers.
- Publication dates are not yet extracted reliably; the UI omits them when
  absent and always shows retrieval time when available.
- DNS is checked before each request and redirect, but a theoretical DNS
  rebinding race remains. The prototype is local-only and fetches provider-found
  public URLs; do not expose this fetcher as a public unauthenticated service.
- In-process background jobs survive a browser reload but not a backend process
  crash. A crashed job may require a local restart or database intervention.
- Google/Gemini quota can stop discovery or comparison. The UI records partial
  failures and abstains; it does not promise offline fact-checking.

### Accepted tradeoffs

- No crawler, source reputation score, vector database, image forensics, or
  cross-encoder is included. None has evaluation evidence justifying its cost.
- Exact excerpts and hashes are persisted instead of whole pages. This reduces
  retained third-party content but cannot recreate a changed page in full.
- Retrieval is capped at 12 pages and 80 passages per claim to fit the 16 GB
  development machine.

## Next validation gate

After the author-reviewed translation gate:

1. use the now-frozen 30 claim cases: ten per source language, balanced across
   numbers, dates, legal attribution, direct announcements, and abstention;
2. record acceptable evidence sets and adjudicated statuses with two distinct
   qualified adjudicators;
3. measure top-five retrieval recall, citation correctness, status correctness,
   abstention, language parity, duplicate handling, and one-page failure
   resilience;
4. run five to eight reader sessions on source inspection and unresolved-claim
   interpretation;
5. only then link **Check claims & context** from translation results.

No evidence-quality claim should be made before those measurements exist.

## Cross-domain claim-selection foundation

Six recent low-stakes general-news articles—two per source language—now have a
frozen set of 21 candidates after deterministic quote, numeric/date, metadata,
polarity, and future-modality checks. Five articles retained three to five
candidates; one short article retained two rather than accepting a weaker
third. All 21 have author review, and all six articles have an acceptable
central/checkable candidate in the top three. This is not independent review.

The existing 15-article NewJeans study is also frozen as a resumable 67-candidate
pool: 24 Vietnamese, 21 English, and 22 Korean candidates. All 67 have author
review. The frozen 30 contains exactly ten claims per language, represents
every article, and has two claims per language in each of five evaluation
categories.

The selection passes and the blank 30-claim adjudication worksheet has been
generated. It is hash-bound to the selection sheet and
requires the exact 30 candidate IDs, ten per language, two distinct reviewers
explicitly labeled independent, a timezone-aware check date, rationale, dated exact evidence
excerpts, and independent publishers and hosts for resolved stances. An
`insufficient` label must document the search scope. No system result is
accepted as its own gold label.

The post-run evaluation path now also rejects missing, duplicated,
cross-role, or stance-inconsistent assessment references. A separate
`newjeans-citation-review.csv` generator binds every cited claim, URL, excerpt,
rank, stance, and role to the exact system-run hash. Its scorer keeps blank,
unsure, author-only, altered, duplicated, and missing judgments out of the
≥90% citation-correctness pass. This tooling is tested, but no real citation
judgment exists until the frozen 30-claim run is complete.

The frozen-run command is also implemented. It currently refuses network use
at the incomplete gold gate. It will not run until the
translation, immutable selection, and gold gates pass; binds checkpoints to
the exact evaluation inputs and pipeline; resumes completed claims; records
runtime and provider failures; and pauses without scoring a quota-exhausted
claim. Its CLI requires an explicit one-to-five-claim batch. This bounds
accidental requests but cannot verify the billing state of the configured
Google account, so “free-only” remains a human preflight requirement.

## Author evidence pilot

An explicitly separate author/AI-assisted pass now covers all 30 frozen claims.
Its validator reports 25 `supported`, three `mixed`, one `disputed`, and one
`insufficient` label across exactly ten claims per language. The pass identified
four concrete refinements: distinguish appearance from official confirmation,
resolve relative dates against publication dates, compare compound timelines
part by part, and abstain on unauthenticated screenshots.

The pilot is useful for workflow and UX refinement only. Its schema does not
contain independent adjudicators, it cannot pass the gold validator, and its
summary always reports `independent_gold_ready: false`. The original independent
worksheet remains blank and continues to block the frozen network run and all
accuracy claims.

The first pilot-driven UX pass is implemented. Mixed results compare both sides
in one view; unresolved results state what evidence rule was not met; readers
can inspect the exact EN/VI/KO searches; source cards distinguish publication
and retrieval dates and expose missing dates; and attributed claims are labeled
as reported statements. Evidence comparison now receives publication dates and
explicitly treats appearance versus confirmation, legal procedural states,
relative dates, and changing counts as material distinctions. Component,
responsive browser, type, lint, and production-build checks pass. Phrase-level
decomposition of compound claims remains future work.
