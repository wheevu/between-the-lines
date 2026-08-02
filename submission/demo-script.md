# Two-minute submission video

The organizer requires a two-minute video or vlog. This script is timed to
finish in 115–120 seconds without speeding through limitations. Replace only
the bracketed measured result after its gate passes.

## Current release path

Claim Trace is reviewer-only until the independent gold, citation, and reader
gates pass. If any of those gates is still open on recording day, keep the
translation sequence below and replace 0:55–1:54 with the architecture view.
Say that multilingual evidence retrieval is implemented behind an evaluation
gate; do not select a claim or show an author-run result as independently
validated.

The nine completed analyses in `api/evaluation/reviewer-guide.md` are the
network-free translation fallback. They load from SQLite and do not call
Gemini. Before recording, make a local, ignored backup and verify every linked
analysis:

```sh
mkdir -p api/data/demo-fallback
sqlite3 api/data/between-the-lines.sqlite3 \
  ".backup 'api/data/demo-fallback/between-the-lines.sqlite3'"

cd api
.venv/bin/python scripts/verify_demo_fallback.py
BTL_DATA_DIR="$PWD/data/demo-fallback" .venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000
```

The validator opens SQLite in read-only mode, runs `PRAGMA integrity_check`,
and requires all nine reviewer-guide analyses to contain complete saved results
for both target-language tabs. The prepared backup is local-only and ignored by
Git. Do not publish it: it contains stored article text and review records. The
fallback was verified on 30 July 2026 with the validator and API health. Rebuild
it after any final review changes.

This command deliberately leaves Claim Trace disabled. The current backup has
no completed Claim Trace result, so use the architecture view while its evidence
gates remain open. Do not enable the route or present the translation fallback
as a stored evidence result.

## 0:00–0:15 — one reader, one problem

“When I read news across Vietnamese, English, and Korean, a translation can
sound fluent while quietly changing who said something, how certain it was, or
which number and date apply. Checking the same claim across three languages is
also slow.”

Show one frozen source sentence beside the selected-language translation.

## 0:15–0:36 — the translation loop

“Between the Lines accepts an article or public URL and translates it into the
language I choose. It checks protected facts such as numbers and negation, and
shows grounded language notes only when it can point to the exact words in
both versions. There is no unexplained confidence score.”

Open one meaning-risk note from the documented author-reviewed set. Do not call
that review independent.

## 0:36–0:55 — ambiguity, not automatic correction

“This marker does not claim the translation is wrong. It explains the possible
change, shows the original phrase, and leaves the correction to the reader.
Numbers and negation also have deterministic checks.”

Show the source, translation, explanation, and alternative together.

## 0:55–1:54 — choose one branch

Use the architecture-only branch while any Claim Trace gate is open. Use the
Claim Trace branch only after the independent gold, citation, and reader gates
all pass.

### Open gates: architecture-only fallback

#### 0:55–1:14 — a separate, gated path

“Claim Trace is a separate path behind an evaluation gate. It starts only after
a reader chooses a quoted factual claim. Opinions and predictions are excluded,
and attributed statements keep the name of the speaker.”

Show the architecture diagram from the reader’s claim to multilingual search.

#### 1:14–1:39 — bounded evidence handling

“The design searches across English, Vietnamese, and Korean, rejects unsafe
URLs, reads a bounded set of pages, and ranks short passages locally. Repeated
or credited reporting is grouped so copies do not look like independent
confirmation.”

Follow the diagram through retrieval, local E5 ranking, and lineage grouping.

#### 1:39–1:54 — the boundary

“That path is implemented, but its independent evidence and reader studies are
not finished. It stays off in the public reader. The system shows uncertainty
instead of turning missing evidence into a verdict.”

End on the server gate and the unresolved-evidence branch. Do not show a Claim
Trace result.

### Gates passed: Claim Trace demonstration

#### 0:55–1:14 — the reader chooses the claim

“Translation quality and factual evidence are separate. The reader chooses a
quoted factual claim; nothing is preselected. Opinions and predictions are
excluded, while attributed statements preserve who made the statement.”

Select one adjudicated claim from the frozen evaluation set.

#### 1:14–1:39 — evidence across three languages

“The system searches in English, Vietnamese, and Korean, reads a bounded number
of pages, groups repeated reporting, and ranks passages locally. It shows exact
excerpts, publishers, dates, languages, failed sources, and limitations.”

Open the strongest evidence source, then show a duplicate or failed source.

#### 1:39–1:54 — restrained outcome and local AI

“A status needs two publishers and two independent evidence clusters. Weak
evidence produces ‘not enough reliable evidence,’ not a guessed verdict.
Multilingual E5 ranking can run through PyTorch or OpenVINO on the laptop.”

Do not mention an Intel speedup unless the named Intel benchmark passes.

## 1:54–2:00 — measured close

“In our frozen evaluation, [INSERT ONE MEASURED READER OR RETRIEVAL RESULT].
Between the Lines helps people inspect meaning and evidence; people still make
the final judgment.”

If any evidence or reader gate remains open on recording day, use:

“The prototype is ready for independent evaluation. It helps people inspect
meaning and evidence; people still make the final judgment.”

## Recording checklist

- Keep the finished edit at or below 2:00.
- Use a finding already judged useful in the stored review set and label the
  reviewer role accurately.
- Keep labels and excerpts legible at normal playback speed.
- Do not say “accurate,” “detects misinformation,” “offline,” or “Intel
  speedup” without the required report.
- Credit third-party models, papers, and source articles in the end frame or
  video description.

While any Claim Trace gate is open:

- Use the architecture-only 0:55–1:54 branch. No adjudicated claim or completed
  Claim Trace result is required.
- Run `scripts/verify_demo_fallback.py` and confirm all nine translation
  analyses pass before using the stored fallback.
- Leave Claim Trace disabled and do not present the translation backup as an
  evidence result.

Only after every Claim Trace gate passes:

- Use a claim from the adjudicated 30-claim set.
- Keep a completed Claim Trace result for recording-day network failure and
  label it as stored when shown.
