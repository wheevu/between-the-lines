# Optional presentation outline

The public 2026 entry page requires a two-minute video, not a slide deck. Keep
this outline for judging, mentoring, or a later national presentation. Preserve
this evidence order.

## 1. One reader, one recurring problem

- Cross-language news reader
- Fluent translation can hide attribution, certainty, number, date, and
  cultural-context changes
- Source checking across three languages is slow and repetitive

Visual: one sentence with the exact changed phrase in EN/VI/KO.

## 2. Complete narrow workflow

Article → aligned translation → phrase worth checking → reader-selected claim →
multilingual evidence → local ranking → inspectable result → human action.

Visual: architecture flow, not a feature grid.

## 3. What is technically distinctive

- sentence-aligned Gemini translation;
- one reader-selected target and grounded language notes;
- deterministic number/negation guards;
- multilingual E5 retrieval and duplicate-aware local ranking;
- conservative status rules independent of the generative stance label;
- OpenVINO runtime path.

## 4. What was measured

Separate:

- controlled regression fixtures;
- 15-article iterative UX study;
- bilingual passage review;
- frozen six-article general-news claim review;
- 30-claim evidence evaluation;
- reader sessions.

Show denominators, misses, and EN/VI/KO breakdown. Pending evidence does not
appear as a positive result.

## 5. Responsible AI by design

- exact quotes and citations;
- no preselection, publisher trust score, or article truth score;
- independent-source and duplicate rules;
- abstention and visible limitations;
- transient full pages and local excerpt ranking;
- correction and better-source feedback.

Visual: cloud/local/transient/stored data map.

## 6. Why Intel

- ordinary-laptop local ranking;
- same frozen workload and model;
- PyTorch versus OpenVINO results on a named Intel device;
- latency, throughput, memory, precision, and ranking agreement.

If the Intel benchmark is pending, label the slide “measurement plan” and do
not show the M1 comparison as Intel evidence.

## 7. Impact and next boundary

Use measured reader-task completion and time saved. Explain the narrow next
step supported by the evaluation. Do not claim universal fact-checking or
misinformation prevention.
