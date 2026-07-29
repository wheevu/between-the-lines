import argparse
import json
from pathlib import Path

from app.ambiguity import build_flags
from app.models import GeminiNote, Language

DEFAULT_CASES = Path(__file__).parents[1] / "evaluation" / "cases.jsonl"


def evaluate(path: Path) -> dict[str, object]:
    true_positive = 0
    false_positive = 0
    false_negative = 0
    exact_cases = 0
    details = []

    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        expected = set(case["expected"])
        flags = build_flags(
            source_text=case["source_text"],
            primary_text=case["primary_text"],
            source_language=Language(case["source_language"]),
            target_language=Language(case["target_language"]),
            notes=[GeminiNote.model_validate(note) for note in case["notes"]],
            shadow_similarity=0.95,
            back_translation_similarity=None,
        )
        actual = {f"{flag.kind.value}:{flag.category.value}" for flag in flags}
        true_positive += len(expected & actual)
        false_positive += len(actual - expected)
        false_negative += len(expected - actual)
        exact_cases += actual == expected
        details.append(
            {
                "id": case["id"],
                "passed": actual == expected,
                "expected": sorted(expected),
                "actual": sorted(actual),
            }
        )

    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "cases": len(details),
        "exact_cases": exact_cases,
        "exact_case_rate": _ratio(exact_cases, len(details)),
        "label_precision": precision,
        "label_recall": recall,
        "details": details,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ambiguity flags on controlled pairs.")
    parser.add_argument("cases", nargs="?", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.cases), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
