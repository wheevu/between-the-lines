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
network-free fallback. They load from SQLite and do not call Gemini. Before
recording, make a local, ignored backup and verify one completed result:

```sh
mkdir -p api/data/demo-fallback
sqlite3 api/data/between-the-lines.sqlite3 \
  ".backup 'api/data/demo-fallback/between-the-lines.sqlite3'"
sqlite3 api/data/demo-fallback/between-the-lines.sqlite3 'PRAGMA integrity_check;'

cd api
BTL_DATA_DIR="$PWD/data/demo-fallback" .venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000
```

The prepared backup is local-only and ignored by Git. Do not publish it: it
contains stored article text and review records. The fallback was verified on
30 July 2026 with `PRAGMA integrity_check`, API health, and a completed saved
analysis. Rebuild it after any final review changes.

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

## 0:55–1:14 — the reader chooses the claim

“Translation quality and factual evidence are separate. The reader chooses a
quoted factual claim; nothing is preselected. Opinions and predictions are
excluded, while attributed statements preserve who made the statement.”

Select one adjudicated claim from the frozen evaluation set.

## 1:14–1:39 — evidence across three languages

“The system searches in English, Vietnamese, and Korean, reads a bounded number
of pages, groups repeated reporting, and ranks passages locally. It shows exact
excerpts, publishers, dates, languages, failed sources, and limitations.”

Open the strongest evidence source, then show a duplicate or failed source.

## 1:39–1:54 — restrained outcome and local AI

“A status needs two publishers and two independent evidence clusters. Weak
evidence produces ‘not enough reliable evidence,’ not a guessed verdict.
Multilingual E5 ranking can run through PyTorch or OpenVINO on the laptop.”

Do not mention an Intel speedup unless the named Intel benchmark passes.

## 1:54–2:00 — measured close

“In our frozen evaluation, [INSERT ONE MEASURED READER OR RETRIEVAL RESULT].
Between the Lines helps people inspect meaning and evidence; people still make
the final judgment.”

If no human result has passed by recording day, use:

“The prototype is ready for independent evaluation. It helps people inspect
meaning and evidence; people still make the final judgment.”

## Recording checklist

- Keep the finished edit at or below 2:00.
- Use a finding already judged useful in the stored review set and label the
  reviewer role accurately.
- Use a claim from the adjudicated 30-claim set.
- Show a stored completed result if venue or recording-day quota is unavailable
  and label it as stored.
- Confirm the fallback database returns `ok` from `PRAGMA integrity_check` and
  opens a completed reviewer-guide analysis before recording.
- Keep labels and excerpts legible at normal playback speed.
- Do not say “accurate,” “detects misinformation,” “offline,” or “Intel
  speedup” without the required report.
- Credit third-party models, papers, and source articles in the end frame or
  video description.
