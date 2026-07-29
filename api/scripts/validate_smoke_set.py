import json
from pathlib import Path

from app.article import extract_article
from app.config import load_settings
from app.models import Language

MANIFEST = Path(__file__).parents[1] / "evaluation" / "cross-domain-smoke.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text())
    settings = load_settings()
    failures: list[str] = []

    for case in data["cases"]:
        try:
            Language(case["source_language"])
            article = extract_article(case["url"], settings)
            words = len(article.text.split())
            if words > settings.max_article_words:
                failures.append(f"{case['id']}: {words} words exceeds {settings.max_article_words}")
                continue
            print(f"{case['id']}: {words} words — {article.title}")
        except Exception as error:
            failures.append(f"{case['id']}: {error}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
