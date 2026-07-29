# Credits, models, and external material

Between the Lines is an original prototype assembled for the Intel Vietnam AI
Impact Festival. It uses third-party models, libraries, articles, and research;
those components are not presented as the entrant’s own work.

## AI models and services

- Google Gemini 3.1 Flash-Lite provides primary translation, structured
  language notes, claim/query generation, grounded URL discovery, and evidence
  comparison through the Google GenAI API.
- Meta’s
  [NLLB-200 distilled 600M](https://huggingface.co/facebook/nllb-200-distilled-600M)
  is retained only in offline experiments that tested—and rejected—a local
  translation-comparison path. It does not run in the live reader workflow. Its
  model card identifies the license as CC BY-NC 4.0, describes it as a research
  model rather than a production deployment, and warns that it is not intended
  for document or certified translation. The license must be reassessed before
  any commercial use.
- Microsoft’s
  [multilingual E5 small](https://huggingface.co/intfloat/multilingual-e5-small)
  provides local evidence-passage ranking and conservative credited-origin
  alias matching. Its model card
  identifies the license as MIT and notes a 512-token input limit.
- Intel
  [OpenVINO](https://docs.openvino.ai/) is the optional local E5 runtime. The
  default development runtime remains PyTorch unless explicitly switched.

## Research informing the design

- NLLB Team et al., *No Language Left Behind: Scaling Human-Centered Machine
  Translation* (2022).
- Wang et al., *Multilingual E5 Text Embeddings: A Technical Report* (2024).
- Huang, Zhai, and Ji,
  [*CONCRETE: Improving Cross-lingual Fact-checking with Cross-lingual
  Retrieval*](https://aclanthology.org/2022.coling-1.86/) (COLING 2022).
- Peng et al.,
  [*SemEval-2025 Task 7: Multilingual and Crosslingual Fact-Checked Claim
  Retrieval*](https://aclanthology.org/2025.semeval-1.323/) (SemEval 2025).
- Vykopal et al.,
  [*Investigating Language and Retrieval Bias in Multilingual Previously
  Fact-Checked Claim Detection*](https://aclanthology.org/2026.eacl-long.240/)
  (EACL 2026).

## News and evaluation material

Every article in the evaluation manifests retains its publisher, title or case
identifier, URL, publication date where known, and a content hash. Full fetched
evidence pages are not included in the submission package. Short exact excerpts
are retained only for review, evidence, and reproducibility, with links to the
original publisher.

## Software libraries

The implementation uses FastAPI, Pydantic, httpx, Trafilatura, Transformers,
Sentence Transformers, PyTorch, OpenVINO, Svelte, Vite, Vitest, and Playwright.
Their names identify dependencies; they do not imply endorsement of this
project.
