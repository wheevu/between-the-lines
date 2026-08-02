# Responsible-AI statement — working draft

This statement follows the nine principles in the festival’s linked 2026
ethical-AI guidance.

## Intended use

Between the Lines helps a reader notice where news meaning may shift across
English, Vietnamese, and Korean, then inspect evidence for one quoted claim at
a time. It supports reading and source inspection; it does not replace a
translator, journalist, fact-checker, court record, or human judgment.

## Human control

- No factual claim is preselected.
- Opinion, prediction, and vague judgment candidates are disabled or reframed
  as attributed statements.
- The reader chooses one claim.
- Results describe what the sources found support or challenge; they do not
  label a whole article or person true or false.
- Readers can report irrelevant evidence, an unsupported status, a correction,
  or a better source.
- A human always decides what to believe or publish.

## Data handling

| Data | Where processed | Retention |
|---|---|---|
| Source article | Gemini for selected-target translation and grounded notes | Analysis result in local SQLite |
| Protected-fact checks | Local deterministic processing | Flags in local SQLite |
| Evidence ranking and credited-origin alias matching | Local multilingual E5 via PyTorch or OpenVINO | Scores, lineage labels, and selected excerpts only |
| Search queries | Gemini and configured search providers | Stored with the claim result |
| Candidate evidence pages | Bounded local fetcher | Full page transient |
| Selected evidence excerpts | Local processing; top excerpts sent to Gemini for stance comparison | Excerpt, metadata, URL, and hash in local SQLite |
| Reader feedback | Local API and SQLite | Until the local database is deleted |

The system is partly local, not offline. Source text and selected evidence are
sent to Gemini.

## Conservative evidence rules

- The input article cannot cite itself.
- A failed or inaccessible page does not fail the whole claim.
- Duplicate content and near-duplicate syndication clusters are grouped.
- At most three pages per final publisher, 12 pages, and 80 passages are
  considered per claim.
- A supported or disputed status requires at least two distinct publishers in
  two distinct evidence clusters.
- A model-classified “primary” excerpt cannot bypass that independence rule.
- Contradictory evidence is retained.
- Insufficient evidence produces abstention, not a guessed verdict.
- Attributed claims check whether a statement was made, not whether an
  allegation inside it is true.

## Uncertainty communication

- Translation notes and deterministic warnings identify phrases to inspect;
  neither is presented as an accuracy probability.
- Evidence results use “by the sources found.”
- Exact excerpts, language, publisher, source type, retrieval date, available
  publication date, rating, mismatch, and limitations remain visible.
- Partial retrieval failures are shown.
- `checked_at` reminds the reader that reporting can change.
- No publisher trust score or unexplained authority score is displayed.

## Known failure modes

- Generated translation notes and evidence stances are stochastic.
- Search quota or provider failure can prevent discovery.
- Search may miss relevant sources, especially across transliterated names,
  paywalls, deleted pages, and breaking news.
- Publication dates are absent when page metadata is unavailable.
- The local fetcher must remain localhost-only because DNS rebinding remains a
  theoretical race despite private-address checks before requests and redirects.
- In-process background jobs survive browser reloads but not a backend crash.
- The current human review and adjudicated fact-check datasets are incomplete.
- Full fetched pages are not retained, limiting later reproduction if a source
  changes.

## Prompt and input safety

Article and fetched page text are treated as hostile document data in prompts.
Grounding URLs are accepted only from provider metadata, not model-written
citations. URLs with credentials, local/private addresses, oversized bodies,
non-HTML content, and excessive redirects are rejected.

These controls reduce risk but do not make arbitrary public web content safe for
a public multi-user deployment.

## Evaluation policy

Every public metric must include its dataset, denominator, language breakdown,
hardware, and unresolved cases. Controlled fixtures cannot be presented as
real-world accuracy. Apple-silicon OpenVINO results cannot be presented as Intel
performance. Failed gates narrow the claim rather than disappearing from the
report.

## Festival principles crosswalk

### 1. Protect the environment

The prototype uses the smallest local models already sufficient for its narrow
tasks, caps each claim at 12 pages and 80 passages, and avoids adding another
reranker without measured need. The benchmark records runtime and throughput,
but no energy or carbon measurement exists yet. The submission must describe
bounded computation, not claim environmental improvement.

### 2. Promote equity and inclusion

The interface handles English, Vietnamese, and Korean without treating English
as the only visible source of truth. Evaluation is balanced by source language
and reports language gaps. This is language inclusion, not universal
accessibility. A basic keyboard journey, semantic-state check, and contrast
probe now pass; assistive-technology user testing and equivalent-UX evidence
remain pending, and no claim is made about all dialects or communities.

### 3. Design for privacy

Only text necessary for translation and selected evidence comparison is sent to
Gemini. Full fetched evidence pages are transient. Results, feedback, queries,
hashes, and selected excerpts stay in the local SQLite database. The interface
states that the system is cloud-dependent so users can make an informed choice.

### 4. Enable transparency and explainability

Every warning links to exact source and translation phrases. Evidence results
retain exact excerpts, URLs, dates, languages, relevance, stance reasons,
duplicate clusters, provider failures, and limitations. Deterministic
minimum-evidence rules—not a hidden model confidence—produce the displayed
status. Frozen artifacts record model, source, manifest, and workload hashes.

### 5. Advance security, safety, and reliability

The fetcher rejects credentials, local and private network targets, oversized
downloads, non-HTML content, excessive redirects, and self-citation. Article
and page text are treated as untrusted prompt data. Controlled tests cover
partial failures and unsafe feedback targets. The server remains localhost-only
because it has not received a production penetration test and a DNS rebinding
race remains theoretically possible.

Claim Trace API routes are also disabled by default and require the server-side
`BTL_CLAIM_TRACE_ENABLED=1` switch. This limits accidental release; it is not
authentication, and an enabled server must remain in a controlled environment.

The frozen evidence runner refuses to start before the human gates, checkpoints
atomically, caps each invocation at five new claims, and pauses instead of
turning a quota failure into an `insufficient` result. It has no paid-service
fallback. Because software cannot inspect whether the configured Google account
has billing enabled, the project author must confirm free-tier quota before
each batch; the project does not claim that this check is automated.

### 6. Enable human oversight

No factual claim is preselected. The reader chooses one claim,
inspects the source evidence, and can report a bad excerpt, incorrect status,
correction, or better source. The system abstains when its evidence rules fail.
No automated result decides what a person should believe or publish.

### 7. Respect human rights

The system does not assign truth or trust scores to people, publishers, or
whole articles. It is not intended for surveillance, profiling, moderation,
legal adjudication, or high-stakes decisions. Its proposed SDG relationship is
limited to helping readers inspect publicly available information under target
16.10.

### 8. Ensure data integrity and mitigate bias

Source quotes must occur in frozen article segments; added numbers, dates,
negation, and future modality are rejected. Evidence requires independent
publishers and duplicate clusters. Evaluation uses equal EN/VI/KO claim counts,
separate language metrics, source hashes, independent adjudicators, and explicit
unknown outcomes. This measures some language and retrieval bias; it does not
eliminate model bias.

### 9. Avoid plagiarism and provide credit

The [credits record](credits.md) identifies the external models, services,
research, libraries, licenses, and news sources used. Exact article and evidence
excerpts retain publisher links. Model-generated output is not presented as
human-authored research or as an original source.
