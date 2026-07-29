import argparse
import json
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.models import Language

SOURCE = Path(__file__).parents[1] / "evaluation" / "claim-trace-corpus.json"
DEFAULT_OUTPUT = Path(__file__).parents[1] / "evaluation" / "claim-trace-robustness-corpus.json"
WINDOW_START = "2026-01-25"
WINDOW_END = "2026-07-25"

LOCALES = {
    Language.ENGLISH: ("en-US", "US", "US:en"),
    Language.VIETNAMESE: ("vi", "VN", "VN:vi"),
    Language.KOREAN: ("ko", "KR", "KR:ko"),
}

QUERIES = {
    "korea-ai-basic-act-implementation": {
        "en": "South Korea AI Basic Act",
        "vi": "Luật AI cơ bản Hàn Quốc",
        "ko": "한국 AI기본법",
    },
    "vietnam-ai-law-effective": {
        "en": "Vietnam artificial intelligence law",
        "vi": "Luật Trí tuệ nhân tạo Việt Nam",
        "ko": "베트남 인공지능법",
    },
    "nipah-india-outbreak": {
        "en": "Nipah virus West Bengal",
        "vi": "virus Nipah Tây Bengal",
        "ko": "니파바이러스 서벵골",
    },
    "hantavirus-cruise-ship": {
        "en": "Hantavirus MV Hondius",
        "vi": "virus Hanta tàu Hondius",
        "ko": "한타바이러스 혼디우스",
    },
    "artemis-ii-launch": {
        "en": "NASA Artemis II launch",
        "vi": "NASA Artemis II phóng",
        "ko": "NASA 아르테미스 2호 발사",
    },
    "wmo-five-year-temperature-outlook": {
        "en": "WMO five year temperature outlook",
        "vi": "WMO dự báo nhiệt độ 5 năm",
        "ko": "WMO 5년 기온 전망",
    },
    "nvidia-gtc-vera-rubin": {
        "en": "Nvidia Vera Rubin GTC 2026",
        "vi": "Nvidia Vera Rubin GTC 2026",
        "ko": "엔비디아 베라 루빈 GTC 2026",
    },
    "apple-wwdc26-siri": {
        "en": "Apple Siri WWDC 2026",
        "vi": "Apple Siri WWDC 2026",
        "ko": "애플 시리 WWDC 2026",
    },
    "qs-world-university-rankings-2027": {
        "en": "QS World University Rankings 2027",
        "vi": "xếp hạng đại học QS 2027",
        "ko": "QS 세계대학순위 2027",
    },
    "world-happiness-report-2026": {
        "en": "World Happiness Report 2026",
        "vi": "Báo cáo Hạnh phúc Thế giới 2026",
        "ko": "2026 세계행복보고서",
    },
    "winter-olympics-opening-2026": {
        "en": "Milano Cortina 2026 opening ceremony",
        "vi": "khai mạc Olympic mùa đông 2026",
        "ko": "2026 밀라노 코르티나 개막식",
    },
    "world-cup-final-2026": {
        "en": "Spain Argentina World Cup final 2026",
        "vi": "Tây Ban Nha Argentina chung kết World Cup 2026",
        "ko": "스페인 아르헨티나 월드컵 결승 2026",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expand the frozen event corpus with resolved publisher URLs."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decode-interval", type=float, default=0.2)
    return parser.parse_args()


def rss_candidates(query: str, language: Language) -> list[dict[str, str]]:
    hl, gl, ceid = LOCALES[language]
    dated_query = f"{query} after:{WINDOW_START} before:2026-07-26"
    params = urlencode({"q": dated_query, "hl": hl, "gl": gl, "ceid": ceid})
    request = Request(
        f"https://news.google.com/rss/search?{params}",
        headers={"User-Agent": "BetweenTheLinesCorpus/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        root = ElementTree.fromstring(response.read())
    candidates = []
    for item in root.findall("./channel/item"):
        source = item.find("source")
        candidates.append(
            {
                "title": unescape(item.findtext("title", "")).strip(),
                "google_news_url": item.findtext("link", "").strip(),
                "publisher": source.text.strip() if source is not None and source.text else "",
                "publisher_url": source.attrib.get("url", "") if source is not None else "",
                "published": _rss_date(item.findtext("pubDate", "")),
            }
        )
    return candidates


def _rss_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()
    except ValueError:
        return ""


def resolve_url(google_news_url: str, interval: float) -> str | None:
    try:
        from googlenewsdecoder import new_decoderv1
    except ImportError as error:
        raise RuntimeError(
            "Install googlenewsdecoder in a temporary environment to build the corpus."
        ) from error
    result = new_decoderv1(google_news_url, interval=interval)
    if not result.get("status"):
        return None
    url = result.get("decoded_url", "")
    host = urlparse(url).hostname or ""
    return url if url.startswith(("http://", "https://")) and host != "news.google.com" else None


def build(interval: float) -> dict[str, object]:
    source = json.loads(SOURCE.read_text())
    failures = []
    events = []
    language_totals = {language.value: 0 for language in Language}
    for event_index, event in enumerate(source["events"]):
        articles = [dict(article, selection="frozen_core") for article in event["articles"]]
        seen_urls = {article["url"] for article in articles}
        seen_hosts = {urlparse(article["url"]).hostname for article in articles}
        for language_index, language in enumerate(Language):
            needed = 3 if language_index == event_index % 3 else 2
            query = QUERIES[event["id"]][language.value]
            added = 0
            for candidate in rss_candidates(query, language):
                if added >= needed:
                    break
                resolved = resolve_url(candidate["google_news_url"], interval)
                if not resolved or resolved in seen_urls:
                    continue
                host = urlparse(resolved).hostname
                if host in seen_hosts:
                    continue
                article_id = f"{event['id']}-{language.value}-robust-{added + 1}"
                articles.append(
                    {
                        "id": article_id,
                        "source_language": language.value,
                        "publisher": candidate["publisher"],
                        "published": candidate["published"],
                        "title": candidate["title"],
                        "url": resolved,
                        "source_type": "web",
                        "credited_origin": None,
                        "edge_tags": ["machine_discovered", "relevance_review_required"],
                        "selection": "robustness_candidate",
                    }
                )
                seen_urls.add(resolved)
                seen_hosts.add(host)
                added += 1
            if added < needed:
                failures.append(
                    {
                        "event_id": event["id"],
                        "language": language.value,
                        "needed": needed,
                        "added": added,
                    }
                )
        for article in articles:
            language_totals[article["source_language"]] += 1
        events.append(
            {key: value for key, value in event.items() if key not in {"articles", "trace_cases"}}
            | {"articles": articles}
        )
        print(f"{event['id']}: {len(articles)} articles")
    return {
        "schema_version": 1,
        "prepared": "2026-07-25",
        "purpose": (
            "Robustness shell for extraction, language routing, clustering, and "
            "source-lineage stress tests; not a factual gold set."
        ),
        "window": {"start": WINDOW_START, "end": WINDOW_END},
        "selection_rules": [
            "Retain the 36-article frozen core.",
            "Add unique publisher domains discovered in language-localized Google News RSS.",
            "Resolve every aggregator wrapper to the publisher URL.",
            "Require manual relevance review before factual scoring.",
        ],
        "events": events,
        "summary": {
            "events": len(events),
            "articles": sum(len(event["articles"]) for event in events),
            "languages": language_totals,
            "unfilled_slots": failures,
        },
    }


def main() -> None:
    args = parse_args()
    result = build(args.decode_interval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
