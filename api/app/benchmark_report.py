from pathlib import Path


def compare_embedding_results(
    torch_result: dict[str, object],
    openvino_result: dict[str, object],
) -> dict[str, object]:
    limitations: list[str] = []
    if torch_result.get("backend") != "torch":
        limitations.append("The PyTorch input is not labeled as the torch backend.")
    if openvino_result.get("backend") != "openvino":
        limitations.append("The OpenVINO input is not labeled as the openvino backend.")

    torch_workload = torch_result.get("workload_sha256")
    openvino_workload = openvino_result.get("workload_sha256")
    if not torch_workload or torch_workload != openvino_workload:
        limitations.append("The two results do not use the same frozen workload.")
    if not torch_result.get("model") or torch_result.get("model") != openvino_result.get("model"):
        limitations.append("The two results do not use the same embedding model.")
    if not torch_result.get("precision") or torch_result.get("precision") != openvino_result.get(
        "precision"
    ):
        limitations.append("The two results do not use the same declared precision.")

    torch_machine = torch_result.get("machine")
    openvino_machine = openvino_result.get("machine")
    torch_fingerprint = (
        torch_machine.get("fingerprint") if isinstance(torch_machine, dict) else None
    )
    same_machine = (
        isinstance(torch_machine, dict)
        and isinstance(openvino_machine, dict)
        and isinstance(torch_fingerprint, str)
        and bool(torch_fingerprint)
        and torch_fingerprint == openvino_machine.get("fingerprint")
    )
    if not same_machine:
        limitations.append("The two results were not recorded on the same machine.")
    intel_detected = (
        isinstance(torch_machine, dict)
        and isinstance(openvino_machine, dict)
        and torch_machine.get("intel_hardware_detected") is True
        and openvino_machine.get("intel_hardware_detected") is True
    )
    if not intel_detected:
        limitations.append("The recorded CPU is not explicitly identified as Intel.")

    torch_runs = _integer(torch_result.get("runs"))
    openvino_runs = _integer(openvino_result.get("runs"))
    if min(torch_runs, openvino_runs) < 10:
        limitations.append("Run each backend at least 10 times.")
    if (
        torch_result.get("warmup_excluded") is not True
        or openvino_result.get("warmup_excluded") is not True
    ):
        limitations.append("Both results must record an excluded warm-up run.")

    torch_top = torch_result.get("top_5_passage_indexes")
    openvino_top = openvino_result.get("top_5_passage_indexes")
    agreement = _top_five_agreement(torch_top, openvino_top)
    if agreement != 1:
        limitations.append("Top-five ranking agreement is below 100%.")

    torch_latency = _median_latency(torch_result)
    openvino_latency = _median_latency(openvino_result)
    speed_ratio = (
        round(torch_latency / openvino_latency, 3)
        if torch_latency > 0 and openvino_latency > 0
        else None
    )
    claim_allowed = not limitations
    return {
        "torch_result": str(torch_result.get("result_path", "")),
        "openvino_result": str(openvino_result.get("result_path", "")),
        "workload_sha256": torch_workload if torch_workload == openvino_workload else None,
        "same_machine": same_machine,
        "intel_hardware_detected": intel_detected,
        "runs": {"torch": torch_runs, "openvino": openvino_runs},
        "median_latency_ms": {
            "torch": torch_latency,
            "openvino": openvino_latency,
        },
        "torch_to_openvino_speed_ratio": speed_ratio,
        "top_5_exact_agreement": agreement,
        "intel_performance_claim_allowed": claim_allowed,
        "intel_speedup_claim_allowed": claim_allowed
        and speed_ratio is not None
        and speed_ratio > 1,
        "limitations": limitations,
    }


def load_result(path: Path) -> dict[str, object]:
    import json

    result = json.loads(path.read_text())
    result["result_path"] = str(path)
    return result


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _median_latency(result: dict[str, object]) -> float:
    latency = result.get("latency_ms")
    if not isinstance(latency, dict):
        return 0
    median = latency.get("median")
    return float(median) if isinstance(median, int | float) else 0


def _top_five_agreement(torch_top: object, openvino_top: object) -> float | None:
    if (
        not isinstance(torch_top, list)
        or not isinstance(openvino_top, list)
        or len(torch_top) != len(openvino_top)
        or not torch_top
    ):
        return None
    return round(
        sum(left == right for left, right in zip(torch_top, openvino_top, strict=True))
        / len(torch_top),
        3,
    )
