# Author/AI-assisted evidence pilot

Date: 24 July 2026  
Scope: the frozen 30 NewJeans claims, ten each in Vietnamese, English, and
Korean

## Result

The separate pilot artifact passes its structural gate:

| Pilot status | Claims |
| --- | ---: |
| Supported | 25 |
| Mixed | 3 |
| Disputed | 1 |
| Insufficient | 1 |

This is an exploratory author review with AI-assisted source discovery. It is
not independent gold and is not a measurement of Between the Lines.

## What the pass exposed

1. **Appearance is not confirmation.** Minji appeared in the four-member
   anniversary content, but contemporaneous reports said her return was still
   unconfirmed. The claim that all four members had confirmed their return is
   therefore `disputed`.
2. **Relative dates are dangerous.** A March article's “early last month”
   description conflicts with contemporaneous December reports placing the
   43.1 billion won filing on December 30. That claim is `mixed`.
3. **Compound timelines need part-level comparison.** Haerin and Hyein were
   confirmed in November, Hanni in December, and Danielle's contract was ended
   in December. Compressing those events into one November announcement earns a
   `mixed` label.
4. **Publisher dates can conflict.** Reports disagree on whether one lawsuit
   was filed December 29 or 30. The prototype should expose the conflict rather
   than choose a date silently.
5. **A screenshot is context, not proof.** The Copenhagen studio-booking claim
   rests on an unauthenticated circulating image, conflicting date ranges, and
   no agency confirmation of studio use. It remains `insufficient`.
6. **Attribution is narrower than truth.** The plagiarism claims are supported
   only as accurate descriptions of filed allegations. The pilot does not
   conclude that plagiarism occurred.
7. **Dynamic counts need timestamps.** Matching reports support the Instagram
   totals at the stated one-day checkpoint, but the counts are not durable
   facts.

## Product implications

The first refinement pass now:

- labels attributed claims as **Reported statement** rather than implying the
  allegation itself was proved;
- places supporting and challenging passages together for `mixed` results;
- explains why `insufficient` remains unresolved and shows the exact
  multilingual search scope;
- exposes publication-date gaps, retrieval dates, direct evidence, source
  lineages, and material mismatches in plain language;
- keeps the article's exact wording available without making it compete with
  the standalone claim;
- passes publication dates into evidence comparison and explicitly distinguishes
  appearance from confirmation, allegation from ruling, relative dates, and
  time-sensitive counts.

Part-level claim decomposition remains a later refinement. The current view
separates evidence on both sides but does not yet highlight the smallest
supported or disputed phrase inside a compound claim.

## Boundary and next gate

Run the structural check from `api/`:

```sh
.venv/bin/python scripts/validate_author_evidence_pilot.py
```

The independent worksheet remains
`newjeans-evidence-adjudication.json`. Two qualified reviewers must complete
that separate file before the frozen system run or any accuracy calculation.
The pilot must never be copied into the independent adjudicators' fields.
