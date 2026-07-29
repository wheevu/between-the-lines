# Intel Vietnam AI Impact Festival 2026 requirements

Checked: 30 July 2026

## Authoritative entry information

The [2026 Vietnam organizer page](https://shtpic.org/vi/intel-vietnam-al-impact-festival-2026/)
identifies the program as a collaboration among the National Innovation Center
(NIC), Saigon Hi-Tech Park (SHTP), SHTP Innovation Center, and Intel Vietnam.
Its theme is “Enriching lives with AI innovation.”

For the student category, an entrant must:

- be at least 18 and currently enrolled in a university, college,
  pre-university, or equivalent program;
- enter alone or in a team of no more than three students;
- submit through the linked Google Form by **25 August 2026**;
- provide a project name of no more than 10 words;
- provide a project description of no more than 150 words;
- provide a two-minute video or vlog;
- provide the requested consent form with an authorized signature.

The form still requires a Google sign-in. Its consent template and any
upload-specific restrictions must be checked by the entrant while signed in;
they are not visible on the public organizer page.

The page says three AI solutions in each age category will receive national
recognition. The highest-ranked team in each category may represent Vietnam at
the Intel AI Global Impact Festival 2026. It lists a 13,000,000 VND cash award
and certificate for each member of a winning team.

## Published evaluation rubric

The organizer links a four-page
[evaluation rubric](https://drive.google.com/file/d/1gCYKVKU2nWTmMZ6mSAGkanWC8js962j1/view?usp=sharing)
worth 50 points:

| Metric | Points | What it rewards |
|---|---:|---|
| Enriching Lives — Impact & Inclusion | 15 | Defined and cited problem, target audience, equivalent UX, accessibility, affordability, low-bandwidth operation, multilingual or multimodal interaction, social impact, necessary AI, SDG mapping, environmental consideration, and sustainability |
| AI Innovation — Application & Implementation | 20 | Non-forced AI use, originality, demonstrated AI knowledge, explained data provenance and use, ethics, privacy, bias mitigation, environment, a working prototype, deployment state, and go-to-market or deployment strategy |
| Technical Knowledge and Skills | 15 | Explained stack, hardware specificity, software and API integration, purpose-built interface, and use of current AI techniques |

Two rows in the published PDF contain internally inconsistent point wording:
the deployment-strategy description mentions up to two points while its range
says one, and the “emerged AI” description mentions four while its range says
three. This package does not silently reinterpret either row. Ask the organizer
if those distinctions affect final preparation.

## Responsible-AI requirements

The organizer links the
[2026 ethical-AI guidance](https://www.sustainablelivinglab.org/view/handbook/guidelines-ethicalai-intelglobalaiimpactfest-2026).
It asks entries to address:

1. environmental protection;
2. equity and inclusion;
3. privacy by design;
4. transparency and explainability;
5. security, safety, and reliability;
6. human oversight;
7. human rights;
8. data integrity and bias mitigation;
9. plagiarism avoidance and proper credit.

The project’s [responsible-AI statement](responsible-ai.md) follows those nine
headings so a reviewer can match design evidence to the festival guidance.

## Between the Lines rubric gaps

The current prototype already demonstrates a purpose-built tri-language
interface, multiple models and APIs, explicit data flow, local inference,
privacy limits, human control, visible evidence, abstention, and a controlled
test suite.

The following evidence is still missing and must not be implied in the video:

- independent reader evidence that the problem and UX matter to the target
  audience;
- assistive-technology user testing and a full screen-reader workflow—the
  current build has basic keyboard, semantic-state, progress, focus, and
  contrast checks only;
- a low-bandwidth or offline claim—the current system is partly local but
  cloud-dependent;
- completed EN/VI/KO translation and evidence-quality gates;
- a public or open-source deployment link;
- a demonstrated sustainability or deployment pathway;
- measured environmental or Intel-device results.

The closest honest SDG mapping is
[SDG target 16.10](https://sdgs.un.org/goals/goal16), public access to
information. Describe the project as supporting readers’ inspection of public
information, not as proving progress on the UN indicator.
