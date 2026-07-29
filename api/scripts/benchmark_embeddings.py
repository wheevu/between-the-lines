import argparse
import json
import platform
import statistics
import subprocess
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

import numpy as np
from sentence_transformers import SentenceTransformer

from app.article import extract_article
from app.config import load_settings
from app.evidence_ranker import chunk_text
from app.models import Language

MODEL_NAME = "intfloat/multilingual-e5-small"
MANIFEST = Path(__file__).parents[1] / "evaluation" / "cross-domain-smoke.json"
QUERIES = [
    "query: Euclid discovered 31 of the oldest quasars documented.",
    "query: Số thí sinh đăng ký các môn STEM trong kỳ thi tốt nghiệp năm 2026 tăng.",
    "query: 쉬엄쉬엄 한강 3종 축제는 6월 5일부터 7일까지 열렸다.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark multilingual E5 on the cross-domain smoke workload."
    )
    parser.add_argument("--backend", choices=["torch", "openvino"], required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_passages() -> list[str]:
    settings = load_settings()
    manifest = json.loads(MANIFEST.read_text())
    passages: list[str] = []
    for case in manifest["cases"]:
        article = extract_article(case["url"], settings)
        language = Language(case["source_language"])
        host = urlparse(article.url).hostname or "source"
        passages.extend(
            f"passage: [{host}] {chunk}" for chunk in chunk_text(article.text, language)
        )
    return passages[:80]


def benchmark(backend: str, runs: int) -> dict[str, object]:
    if runs < 1:
        raise ValueError("--runs must be at least 1.")
    passages = load_passages()
    model_kwargs = {"export": True} if backend == "openvino" else None
    model = SentenceTransformer(
        MODEL_NAME,
        backend=backend,
        device="cpu",
        model_kwargs=model_kwargs,
    )
    payload = [*QUERIES, *passages]
    model.encode(payload, normalize_embeddings=True, show_progress_bar=False)

    timings = []
    embeddings = None
    for _ in range(runs):
        started = perf_counter()
        embeddings = model.encode(
            payload,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        timings.append((perf_counter() - started) * 1_000)
    if embeddings is None:
        raise RuntimeError("The benchmark produced no embeddings.")

    query_embeddings = embeddings[: len(QUERIES)]
    passage_embeddings = embeddings[len(QUERIES) :]
    top_ids = [
        np.argsort(query @ passage_embeddings.T)[::-1][:5].astype(int).tolist()
        for query in query_embeddings
    ]
    median_ms = statistics.median(timings)
    machine = machine_details()
    workload_sha256 = sha256(
        json.dumps(
            {"queries": QUERIES, "passages": passages},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "model": MODEL_NAME,
        "backend": backend,
        "precision": "runtime default; do not label INT8",
        "machine": machine,
        "software": {
            "python": platform.python_version(),
            "sentence_transformers": package_version("sentence-transformers"),
            "torch": package_version("torch"),
            "openvino": package_version("openvino"),
        },
        "manifest_sha256": sha256(MANIFEST.read_bytes()).hexdigest(),
        "workload_sha256": workload_sha256,
        "queries": len(QUERIES),
        "passages": len(passages),
        "runs": runs,
        "warmup_excluded": True,
        "latency_ms": {
            "median": round(median_ms, 2),
            "minimum": round(min(timings), 2),
            "maximum": round(max(timings), 2),
        },
        "passages_per_second": round(len(passages) / (median_ms / 1_000), 2),
        "top_5_passage_indexes": top_ids,
        "intel_performance_claim_allowed": False,
        "claim_limitation": (
            "A single backend result cannot support an Intel performance claim. "
            "Compare both backends with compare_embedding_benchmarks.py."
        ),
    }


def machine_details() -> dict[str, object]:
    system = platform.system()
    processor = platform.processor().strip()
    vendor = ""
    model = processor
    if system == "Darwin":
        model = _command_value(["sysctl", "-n", "machdep.cpu.brand_string"]) or processor
        vendor = "Apple" if "apple" in model.casefold() else ""
    elif system == "Linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            values = {}
            for line in cpuinfo.read_text(errors="replace").splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    values.setdefault(key.strip(), value.strip())
            vendor = values.get("vendor_id", "")
            model = values.get("model name", processor)
    elif system == "Windows":
        vendor = processor
    identity = f"{vendor} {model}".casefold()
    intel_detected = "genuineintel" in identity or "intel" in identity
    fingerprint = sha256(
        f"{platform.platform()}|{platform.machine()}|{vendor}|{model}".encode()
    ).hexdigest()
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": processor,
        "cpu_vendor": vendor,
        "cpu_model": model,
        "fingerprint": fingerprint,
        "intel_hardware_detected": intel_detected,
    }


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _command_value(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def main() -> None:
    args = parse_args()
    result = benchmark(args.backend, args.runs)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(f"{rendered}\n")
    print(rendered)


if __name__ == "__main__":
    main()
