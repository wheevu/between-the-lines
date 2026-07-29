# Intel AI PC benchmark runbook

The benchmark code is ready; an Intel result is not yet recorded.

Intel states that its AI PC Cloud provides free, continuous access to an AI PC:
https://www.intel.com/content/www/us/en/developer/topic-technology/ai-pc/download-get-started.html
Account access must be completed by the entrant; this workspace has no Intel
Cloud credentials.

On the assigned Intel machine:

```sh
cd api
python3 -m venv .venv-intel
.venv-intel/bin/pip install -e '.[dev,openvino]'

.venv-intel/bin/python scripts/benchmark_embeddings.py \
  --backend torch --runs 10 \
  --output evaluation/embedding-benchmark-intel-torch.json

.venv-intel/bin/python scripts/benchmark_embeddings.py \
  --backend openvino --runs 10 \
  --output evaluation/embedding-benchmark-intel-openvino.json

.venv-intel/bin/python scripts/compare_embedding_benchmarks.py \
  evaluation/embedding-benchmark-intel-torch.json \
  evaluation/embedding-benchmark-intel-openvino.json \
  --output evaluation/embedding-benchmark-intel-comparison.json
```

The comparator rejects mismatched workloads, different machines, fewer than ten
runs, included warm-ups, non-Intel hardware, or changed top-five results. Report
latency and ranking agreement even if OpenVINO is slower. Do not claim a
speed-up until `intel_speedup_claim_allowed` is true.

OpenVINO’s official guidance supports using Optimum Intel to export Hugging Face
models and recommends converting once rather than at every startup:
https://docs.openvino.ai/nightly/openvino-workflow-generative/inference-with-optimum-intel.html
