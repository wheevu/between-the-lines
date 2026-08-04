# Production schedule to 25 August 2026

The deadline is close enough that every week needs a frozen output. Do not add
new product features unless a scheduled evaluation exposes a specific failure.

## Status: 2 August 2026

- UI phase complete and frozen for the reader study: paste-fallback keeps the
  page link and title, light visual refresh (segmented input control, brand
  mark, error/empty states), label audit against the four reader tasks,
  keyboard-only and zoom-reflow journeys added (18 component tests, ten
  browser journeys). Reopening the interface after this point risks invalidating
  reader-study measures.
- Gold evidence template is hash-bound and contains all 30 claims; the `gold`
  blocks are empty pending two independent adjudicators.

## 24–29 July — translation and claim-selection evidence

- Recruit at least one strong Korean–English reader and one Vietnamese-capable
  reviewer.
- Complete all 12 passage reviews: two target-language reviews in each of the
  six EN/VI/KO directions.
- Decide at least five meaning-risk judgments.
- Review all 21 low-stakes general-news candidates.
- Review all 67 NewJeans candidates and select the structurally balanced 30.
- Run every summary script and preserve failed as well as passing outcomes.

Exit evidence:

- translation readiness JSON summary;
- completed general-news review CSV and summary;
- completed 67-row selection CSV with `ready_for_evidence_adjudication: true`.

## 30 July–4 August — independent gold evidence

- Generate the hash-bound 30-claim adjudication file.
- Have two distinct pseudonymous reviewers explicitly labeled `independent`
  record expected status, exact excerpts, source dates, independence reasoning,
  and search scope.
- Resolve disagreements without looking at Between the Lines output.
- Validate the gold file before running the system.

Exit evidence:

- `newjeans-evidence-adjudication.json`;
- validator output with 30/30 ready claims.

## 5–9 August — frozen system run

- Confirm the configured account's free quota, then use the gated system runner
  in batches of at most five claims; never enable a paid fallback.
- Run the same 30 claims through EN/VI/KO retrieval, local ranking, and evidence
  synthesis.
- Preserve provider failures, raw result JSON, runtime metadata, and check
  dates.
- Review every displayed top citation for relevance and stance correctness.
- Report retrieval, status, abstention, duplicate, failure-resilience, and
  language-parity metrics.
- Fix only a demonstrated failure class; if code changes, rerun the entire
  frozen set and label the new run.

Exit evidence:

- one complete system-run artifact;
- automatic metric summary plus the hash-bound
  `newjeans-citation-review.csv` summary with denominators and counterexamples;
- a final adjudicated demo claim or an explicit decision to omit the factual
  layer from the video.

## 10–14 August — readers and Intel hardware

- Run five to eight observed reader sessions, including one keyboard-only or
  assistive-technology session if available.
- Measure whether readers can distinguish a translation warning from factual
  evidence, find the strongest source, and explain an unresolved result.
- Borrow a named Intel Core or Core Ultra laptop.
- Run at least ten measured PyTorch and ten OpenVINO repetitions on the exact
  frozen workload with excluded warmups.
- Preserve raw JSON. Report no speedup if the comparison gate rejects it.

Exit evidence:

- reader-study notes and aggregate;
- Intel benchmark pair and validated comparison report.

## 15–19 August — freeze the story

- Select one reviewed translation risk and one adjudicated claim.
- Replace submission placeholders only with stored measurements.
- Freeze project name and 150-word description.
- Draft captions, source credits, and the video end frame.
- Run backend, component, browser, build, lint, formatting, dependency, and
  audit checks.

Exit evidence:

- release-candidate evaluation report;
- final responsible-AI statement and credits;
- verified demo URLs and recording fallback.

## 20–23 August — record and inspect the form

- Sign into the official Google Form.
- Download and complete its current consent template.
- Confirm accepted video host/file type, privacy setting, and any upload limits.
- Record the two-minute video from the frozen script.
- Add captions and confirm every source excerpt is legible.
- Have one person unfamiliar with the project watch it once and state the
  problem, AI job, human action, limitation, and measured result.

Exit evidence:

- final video at or below 2:00;
- signed consent;
- completed form draft without submission.

## 24–25 August — buffer and submit

- Recheck every form field, link permission, word count, and video duration.
- Confirm student enrollment details and team membership.
- Submit before the final day where possible.
- Save the confirmation page or email and a copy of every submitted artifact.
