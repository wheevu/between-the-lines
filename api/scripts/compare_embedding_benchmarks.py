import argparse
import json
from pathlib import Path

from app.benchmark_report import compare_embedding_results, load_result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare frozen PyTorch and OpenVINO embedding benchmark results."
    )
    parser.add_argument("torch_result", type=Path)
    parser.add_argument("openvino_result", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    comparison = compare_embedding_results(
        load_result(args.torch_result),
        load_result(args.openvino_result),
    )
    rendered = json.dumps(comparison, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(f"{rendered}\n")
    print(rendered)


if __name__ == "__main__":
    main()
