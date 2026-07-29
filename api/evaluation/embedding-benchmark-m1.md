# Multilingual E5 backend development check

**Machine:** Apple M1 MacBook Air, 16 GB, arm64  
**Date:** 24 July 2026  
**Workload:** three EN/VI/KO queries ranked against 30 passages extracted from
the six-article cross-domain smoke set  
**Model:** `intfloat/multilingual-e5-small`  
**Runs:** one untimed warm-up, then ten measured batches per backend

| Backend | Median batch latency | Passages/s | Top-5 agreement |
|---|---:|---:|---:|
| PyTorch CPU | 1,703.19 ms | 17.61 | baseline |
| OpenVINO CPU | 2,160.39 ms | 13.89 | 100% |

The OpenVINO export ran successfully on Apple silicon and returned the same
top-five passage order for all three queries. It was slower than PyTorch on
this M1 workload. This is a development compatibility result, not an Intel
performance result, and it gives no basis for claiming an Intel speedup.

The raw measurements are in
`embedding-benchmark-m1-torch.json` and
`embedding-benchmark-m1-openvino.json`. Both mark
`intel_performance_claim_allowed` as false. Their input workload hash is
identical. `embedding-benchmark-m1-comparison.json` also refuses both an Intel
performance claim and a speedup claim because this is an Apple M1 and each
development run used ten measured batches.

For the festival measurement, rerun both backends on the same borrowed Intel
Core or Core Ultra laptop, increase to at least 10 measured runs, and add an
explicitly quantized INT8 model. Report warm and cold latency separately and
retain top-k agreement; do not adopt INT8 if retrieval quality falls outside
the evaluation gate.

Create the claim-gated comparison after both runs:

```sh
.venv/bin/python scripts/compare_embedding_benchmarks.py \
  evaluation/embedding-benchmark-intel-torch.json \
  evaluation/embedding-benchmark-intel-openvino.json \
  --output evaluation/embedding-benchmark-intel-comparison.json
```

The comparator requires the same workload hash, embedding model, declared
precision, CPU fingerprint, an explicitly identified Intel CPU, excluded
warm-ups, at least 10 runs per backend, and exact top-five agreement.

## Runtime switch

PyTorch remains the default. After installing the optional dependency, the
local API can use OpenVINO for E5 embeddings:

```sh
cd api
.venv/bin/pip install -e '.[openvino]'
BTL_EMBEDDING_BACKEND=openvino .venv/bin/uvicorn app.main:app
```

The recorded OpenVINO run establishes that this exact environment can execute
the backend on Apple silicon. The project still requires the Intel laptop run
before making Intel-specific performance claims.

References:

- https://docs.openvino.ai/2026/about-openvino/release-notes-openvino/system-requirements.html
- https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html#openvino
