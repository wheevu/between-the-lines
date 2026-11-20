# Between the Lines (`btl`)

Local English, Vietnamese, and Korean verification, cross-script origin clustering, and passage-ranking CLI + stdio MCP engine.

Explore the **[interactive static showcase](https://wheevu.github.io/between-the-lines/)** with six live engine runs (translation drift audits, revision diffing, wire clustering, and candidate passage ranking).

Built to run standalone from the shell or directly inside agent research workflows (OpenCode `deep-research`, T3 Code, Antigravity, and Codex) with zero external LLM calls.

## Capabilities

- **`check_translation`**: Deterministic EN/VI/KO translation drift audits covering numbers and scales (`억`/`만`/`천`/`조`, `tỷ`/`triệu`/`nghìn`, Vietnamese decimal `,`/`.`), negation and polarity equivalents, modality shifts (`asserted` vs `uncertain`/`future`/`denied`), legal-stage drift (`allegation` < `investigation` < `filing` < `ruling` < `finding`), attribution loss, and quote anchoring.
- **`analyze_claims`**: Offset-preserving EN/VI/KO sentence segmentation, facet extraction, candidate claim grounding verification, and search-query anchor checking.
- **`diff_editions`**: Deterministic revision diffing across `number`, `date`, `negation`, `name`, `modality`, `legal_state`, and `terminology` with SHA-256 provenance digests.
- **`cluster_origins`**: Cross-script wire, agency, and institution alias resolution (`Reuters`/`로이터`, `Yonhap`/`연합뉴스`, `WMO`/`세계기상기구`, `VNA`/`TTXVN`, etc.), acronym bridging, near-duplicate excerpt clustering, optional local E5 similarity, and `research_ledger` `origin` batch emission.
- **`extract_and_rank`**: SSRF-safe public HTML extraction (`trafilatura`) and pre-fetched document chunking, near-duplicate tagging, publisher-capped top-K ranking via lazy `intfloat/multilingual-e5-small` (with deterministic lexical fallback and 5-minute idle memory unload), and `candidate`-only `research_ledger` packet emission.

## Quick start

```sh
# Inspect environment, cached models, and registered agent harnesses
./bin/btl doctor --json

# Audit a translation pair
./bin/btl check-translation \
  --source-text "The budget reached 1억 5000만 원." \
  --translation-text "Ngân sách đạt 150 triệu won."

# Run stdio MCP server (used by OpenCode, T3 Code Antigravity, agy, and Codex)
./bin/btl-mcp
```

Optional local installation in editable mode:

```sh
python3 -m pip install -e '.[dev]'
```

## Boundaries

- All five tools are local and make no remote LLM calls.
- `extract_and_rank` fetches only public HTTP(S) HTML/text URLs (blocking private/loopback/link-local IPs across redirects, 2 MB cap) when `urls` are supplied; `published_at_unverified` reports raw page metadata rather than confirmed publication dates.
- Emitted `research_ledger` evidence items are always `status: "candidate"`. Downstream verification and publication remain owned by the calling agent and `research_ledger`.

## Verification

```sh
python3 -m ruff check btl tests
python3 -m pytest -q
./bin/btl doctor --json
```

## Historical prototype records

The earlier 2026 browser-based FastAPI + Svelte prototype code is preserved in Git history (`ba961a5`), and its dated evaluation and responsible-AI reports remain under [`submission/`](submission/README.md) and [`api/evaluation/`](api/evaluation/README.md).
