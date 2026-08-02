# Between the Lines submission workspace

Prepared: 24 July 2026  
Festival target: Intel Vietnam AI Impact Festival, August 2026

This directory contains draft submission material. It is not ready to submit
until every required gate below has measured evidence.

## Current package

- [Official 2026 requirements and rubric map](official-requirements.md)
- [Submission form copy](form-copy.md)
- [Credits, models, and external material](credits.md)
- [Accessibility implementation check](accessibility-check.md)
- [Production schedule to 25 August](production-schedule.md)
- [Reviewer outreach and session brief](reviewer-outreach.md)
- [Evaluation report](evaluation-report.md)
- [Responsible-AI statement](responsible-ai.md)
- [Architecture and data flow](architecture.md)
- [Two-minute video script](demo-script.md)
- [Slide outline](slide-outline.md)

## Release gates

| Gate | Required evidence | Current state |
|---|---|---|
| Translation readiness | 12 real-news passage reviews; two per language direction | 12/12 author reviews; gate passes |
| Meaning-risk usefulness | 5 decided judgments; at least 80% useful | 12/12 useful after documented refinement; author-only |
| General-news claim selection | Review 21 frozen EN/VI/KO candidates | 21/21 author-reviewed; top-three 6/6 articles |
| Thirty-claim benchmark selection | Review 67 frozen candidates; select balanced 10 per language | 67/67 author-reviewed; balanced 30 frozen |
| Evidence quality | 30 adjudicated claims and the published retrieval/status gates | Worksheet frozen; 0/30 gold-ready |
| Reader understanding | 5–8 observed sessions | Not started |
| Intel performance | Same frozen workload, both runtimes, at least 10 runs on a named Intel CPU | No Intel run |
| Translation + architecture recording fallback | All nine reviewer-guide analyses deserialize from an integrity-checked backup | Local backup passes 9/9; no completed Claim Trace result |

Claim Trace is therefore disabled on the server by default and hidden in the
ordinary reader flow. Controlled evaluation runs must explicitly set
`BTL_CLAIM_TRACE_ENABLED=1` and use a `reviewer=author` or
`reviewer=independent` URL. The URL role is self-declared metadata, not
authentication or evidence of independent review.

Do not turn a pending cell into narrative evidence. If a gate fails, narrow the
claim or fix the demonstrated failure and rerun a frozen evaluation.

## Official submission

The public 2026 organizer page sets the deadline at **25 August 2026** and asks
for a project name of at most 10 words, a description of at most 150 words, a
two-minute video or vlog, and a signed consent form through its Google Form.
The form requires Google sign-in, so the entrant must inspect any additional
upload and consent instructions directly.

Before submitting:

1. replace every `[PENDING]` field only from a stored report or raw artifact;
2. complete the signed consent and enrollment details;
3. record and caption the two-minute video;
4. run the complete verification commands in the project README;
5. retain a completed result and screen recording for a network-failure
   fallback.

## Claims check

Allowed now:

- The implementation handles English, Vietnamese, and Korean text.
- Quick translation uses one reader-selected Gemini translation, grounded
  notes, and deterministic protected-fact checks.
- Claim Trace ranks evidence passages locally with multilingual E5.
- NLLB is retained only as a documented offline experiment, not as part of the
  live reader workflow.
- The evidence path is gated, source-bounded, and designed to abstain.
- Controlled tests cover exact quote grounding, source diversity, partial
  failure, feedback, and unsafe Intel-claim prevention.

Not allowed now:

- Translation accuracy or warning precision on real readers.
- Misinformation-detection or fact-check accuracy.
- Production security, full offline operation, or universal URL support.
- Any Intel speed, memory, throughput, or efficiency claim.
