from app.benchmark_report import compare_embedding_results


def result(
    backend: str,
    *,
    intel: bool = True,
    runs: int = 10,
    workload: str = "same-workload",
    top: list[list[int]] | None = None,
) -> dict[str, object]:
    return {
        "model": "intfloat/multilingual-e5-small",
        "backend": backend,
        "precision": "runtime default; do not label INT8",
        "workload_sha256": workload,
        "machine": {
            "fingerprint": "same-machine",
            "intel_hardware_detected": intel,
        },
        "runs": runs,
        "warmup_excluded": True,
        "latency_ms": {"median": 100 if backend == "torch" else 80},
        "top_5_passage_indexes": top or [[1, 2, 3, 4, 5]],
    }


def test_comparison_allows_a_measured_intel_speedup_only_after_all_gates() -> None:
    comparison = compare_embedding_results(result("torch"), result("openvino"))

    assert comparison["intel_performance_claim_allowed"]
    assert comparison["intel_speedup_claim_allowed"]
    assert comparison["torch_to_openvino_speed_ratio"] == 1.25
    assert comparison["limitations"] == []


def test_x86_shape_or_single_short_run_cannot_enable_an_intel_claim() -> None:
    comparison = compare_embedding_results(
        result("torch", intel=False, runs=2),
        result("openvino", intel=False, runs=2),
    )

    assert not comparison["intel_performance_claim_allowed"]
    assert not comparison["intel_speedup_claim_allowed"]
    assert "The recorded CPU is not explicitly identified as Intel." in comparison["limitations"]
    assert "Run each backend at least 10 times." in comparison["limitations"]


def test_different_workloads_or_rankings_block_comparison_claims() -> None:
    comparison = compare_embedding_results(
        result("torch"),
        result(
            "openvino",
            workload="changed",
            top=[[5, 4, 3, 2, 1]],
        ),
    )

    assert not comparison["intel_performance_claim_allowed"]
    assert comparison["top_5_exact_agreement"] == 0
    assert any("same frozen workload" in item for item in comparison["limitations"])
    assert any("ranking agreement" in item for item in comparison["limitations"])
