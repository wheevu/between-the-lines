import re
import unicodedata
from collections import Counter
from hashlib import sha256
from pathlib import Path

from app.config import Settings
from app.evidence_ranker import EvidencePassage, rank_passages
from app.evidence_retrieval import canonicalize_url, retrieve_pages
from app.fact_checker import _evidence_items
from app.local_models import LocalModels
from app.models import DiscoveredSource, DiscoveryMethod, Language, SourceType

ANSWERABILITY = {"answerable", "unanswerable", "uncertain"}
WHITESPACE = re.compile(r"\s+")


def corpus_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def normalize_text(value: str) -> str:
    return WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()


def contains_quote(text: str, quote: str) -> bool:
    return normalize_text(quote) in normalize_text(text)


def validate_recall_oracle(oracle: dict, manifest: dict, manifest_hash: str) -> dict:
    issues: list[str] = []
    if oracle.get("schema_version") != 1:
        issues.append("Use recall-oracle schema version 1.")
    if oracle.get("corpus_sha256") != manifest_hash:
        issues.append("The oracle does not match the frozen corpus.")
    if oracle.get("reviewer_role") != "author":
        issues.append("Label this development oracle with reviewer_role author.")

    expected = _case_contexts(manifest)
    cases = oracle.get("cases")
    if not isinstance(cases, list):
        cases = []
        issues.append("Oracle cases must be a list.")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(case_ids) != len(set(case_ids)):
        issues.append("Remove duplicate oracle cases.")
    if set(case_ids) != set(expected):
        issues.append("Review the exact 24 frozen case IDs.")

    case_issues: list[dict] = []
    counts: Counter[str] = Counter()
    for case in cases:
        if not isinstance(case, dict):
            case_issues.append({"case_id": None, "issues": ["Case must be an object."]})
            continue
        case_id = case.get("case_id")
        context = expected.get(case_id)
        current: list[str] = []
        answerability = case.get("answerability")
        if answerability not in ANSWERABILITY:
            current.append("Choose answerable, unanswerable, or uncertain.")
        else:
            counts[answerability] += 1
        rationale = case.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            current.append("Explain the answerability decision.")
        reviewed = case.get("reviewed_article_ids")
        expected_reviewed = set(context["comparison_ids"]) if context else set()
        if not isinstance(reviewed, list) or set(reviewed) != expected_reviewed:
            current.append("Record both permitted comparison article IDs.")
        passages = case.get("gold_passages")
        if not isinstance(passages, list):
            current.append("gold_passages must be a list.")
            passages = []
        if answerability == "answerable" and not passages:
            current.append("An answerable case needs at least one gold passage.")
        if answerability == "unanswerable" and passages:
            current.append("An unanswerable case cannot contain gold passages.")
        for passage in passages:
            if not isinstance(passage, dict):
                current.append("Each gold passage must be an object.")
                continue
            if passage.get("article_id") not in expected_reviewed:
                current.append("Every gold passage must come from a comparison article.")
            quote = passage.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                current.append("Every gold passage needs a short exact quote.")
            elif len(quote.split()) > 80:
                current.append("Keep each gold quote at or below 80 words.")
        if current:
            case_issues.append({"case_id": case_id, "issues": sorted(set(current))})

    if case_issues:
        issues.append("Complete every oracle case before running diagnostics.")
    return {
        "cases": len(cases),
        "answerability": dict(sorted(counts.items())),
        "case_issues": case_issues,
        "ready_for_diagnostics": not issues,
        "blockers": issues,
    }


def validate_publisher_holdout(
    oracle: dict,
    robustness_manifest: dict,
    core_manifest: dict,
    manifest_hash: str,
) -> dict:
    blockers: list[str] = []
    if oracle.get("schema_version") != 1:
        blockers.append("Use publisher-holdout schema version 1.")
    if oracle.get("corpus_sha256") != manifest_hash:
        blockers.append("The holdout does not match the robustness corpus.")
    if oracle.get("reviewer_role") != "author":
        blockers.append("Label this development holdout with reviewer_role author.")
    cases = oracle.get("cases")
    if not isinstance(cases, list):
        cases = []
        blockers.append("Holdout cases must be a list.")
    if len(cases) != 12:
        blockers.append("Freeze exactly 12 publisher-held-out cases.")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(case_ids) != len(set(case_ids)):
        blockers.append("Remove duplicate holdout case IDs.")

    core_cases = {
        case["id"]: (case, event)
        for event in core_manifest["events"]
        for case in event["trace_cases"]
    }
    robust_articles = {
        article["id"]: (article, event)
        for event in robustness_manifest["events"]
        for article in event["articles"]
        if article.get("selection") == "robustness_candidate"
    }
    case_issues = []
    languages: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    for case in cases:
        current = []
        case_id = case.get("case_id") if isinstance(case, dict) else None
        core = core_cases.get(case_id)
        if core is None:
            current.append("Use a frozen core claim ID.")
        else:
            expected_language = core[0]["seed_language"]
            expected_topic = core[1]["topic"]
            if case.get("source_language") != expected_language:
                current.append("Preserve the frozen claim's source language.")
            if case.get("topic") != expected_topic:
                current.append("Preserve the frozen event topic.")
            languages[expected_language] += 1
            topics[expected_topic] += 1
        article_ids = case.get("evidence_article_ids", [])
        if not isinstance(article_ids, list) or not article_ids:
            current.append("Select at least one robustness article.")
            article_ids = []
        for article_id in article_ids:
            robust = robust_articles.get(article_id)
            if robust is None:
                current.append("Evidence articles must be robustness candidates.")
            elif core is not None and robust[1]["id"] != core[1]["id"]:
                current.append("Evidence articles must cover the same event as the claim.")
        passages = case.get("gold_passages", [])
        if case.get("match_policy") not in {"any", "all"}:
            current.append("Choose an any or all gold-passage match policy.")
        if not isinstance(passages, list) or not passages:
            current.append("Every holdout case needs at least one gold passage.")
            passages = []
        for passage in passages:
            if not isinstance(passage, dict):
                current.append("Every gold passage must be an object.")
                continue
            if passage.get("article_id") not in article_ids:
                current.append("Gold passages must come from selected holdout articles.")
            quote = passage.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                current.append("Every gold passage needs an exact quote.")
            elif len(quote.split()) > 80:
                current.append("Keep each holdout quote at or below 80 words.")
        if not isinstance(case.get("rationale"), str) or not case["rationale"].strip():
            current.append("Explain why the holdout passage is answerable.")
        if current:
            case_issues.append({"case_id": case_id, "issues": sorted(set(current))})
    if languages != Counter({"en": 4, "vi": 4, "ko": 4}):
        blockers.append("Balance the holdout at four cases per source language.")
    expected_topics = {event["topic"] for event in core_manifest["events"]}
    if topics != Counter({topic: 2 for topic in expected_topics}):
        blockers.append("Balance the holdout at two cases per topic.")
    if case_issues:
        blockers.append("Complete every publisher-held-out case.")
    return {
        "cases": len(cases),
        "language_counts": dict(sorted(languages.items())),
        "topic_counts": dict(sorted(topics.items())),
        "case_issues": case_issues,
        "ready_for_retrieval_diagnostics": not blockers,
        "blockers": blockers,
    }


def run_recall_diagnostics(
    manifest: dict,
    oracle: dict,
    baseline: dict,
    settings: Settings,
    local_models: LocalModels,
) -> dict:
    contexts = _case_contexts(manifest)
    baseline_by_id = {result["case_id"]: result for result in baseline["results"]}
    rows = []
    for oracle_case in oracle["cases"]:
        context = contexts[oracle_case["case_id"]]
        comparison_articles = context["comparison_articles"]
        sources = [_source(article) for article in comparison_articles]
        batch = retrieve_pages(
            sources,
            input_url=context["source_article"]["url"],
            settings=settings,
        )
        items = _evidence_items(batch.pages)
        passages = [
            EvidencePassage(item.id, item.excerpt, item.publisher, item.cluster_id)
            for item in items
        ]
        selected = rank_passages(
            context["case"]["seed_claim"],
            passages,
            local_models,
            limit=6,
        )
        similarities = (
            local_models.similarities(
                [context["case"]["seed_claim"]] * len(items),
                [item.excerpt for item in items],
            )
            if items
            else []
        )
        raw_rank = {
            item.id: rank
            for rank, (_, item) in enumerate(
                sorted(
                    zip(similarities, items, strict=True),
                    key=lambda pair: pair[0],
                    reverse=True,
                ),
                start=1,
            )
        }
        selected_ids = {result.passage.id for result in selected}
        baseline_items = baseline_by_id.get(oracle_case["case_id"], {}).get(
            "evidence",
            [],
        )
        page_by_article = _pages_by_article(batch.pages, comparison_articles)
        gold_results = []
        for gold in oracle_case["gold_passages"]:
            page = page_by_article.get(gold["article_id"])
            matching = [
                item
                for item in items
                if page is not None
                and canonicalize_url(str(item.url)) == canonicalize_url(page.url)
                and contains_quote(item.excerpt, gold["quote"])
            ]
            matching_ids = {item.id for item in matching}
            selected_gold_ids = matching_ids & selected_ids
            alignment_states = sorted(
                {
                    item["alignment_state"]
                    for item in baseline_items
                    if selected_gold_ids
                    and page is not None
                    and canonicalize_url(item["url"]) == canonicalize_url(page.url)
                }
            )
            gold_results.append(
                {
                    "article_id": gold["article_id"],
                    "quote_sha256": sha256(gold["quote"].encode()).hexdigest(),
                    "page_readable": page is not None,
                    "gold_in_page": bool(page and contains_quote(page.text, gold["quote"])),
                    "gold_in_chunk": bool(matching),
                    "best_raw_rank": min(
                        (raw_rank[item.id] for item in matching),
                        default=None,
                    ),
                    "selected_top_six": bool(selected_gold_ids),
                    "strictly_aligned": "aligned" in alignment_states,
                    "aligned_or_partial": bool({"aligned", "partial"} & set(alignment_states)),
                    "alignment_states": alignment_states,
                }
            )
        failure_stage = _failure_stage(oracle_case["answerability"], gold_results)
        rows.append(
            {
                "case_id": oracle_case["case_id"],
                "source_language": context["case"]["seed_language"],
                "answerability": oracle_case["answerability"],
                "retrieved_pages": len(batch.pages),
                "candidate_chunks": len(items),
                "retrieval_failures": len(batch.failures),
                "gold": gold_results,
                "failure_stage": failure_stage,
            }
        )
    return {"cases": rows, "summary": summarize_diagnostics(rows)}


def run_holdout_retrieval_diagnostics(
    core_manifest: dict,
    robustness_manifest: dict,
    oracle: dict,
    settings: Settings,
    local_models: LocalModels,
) -> dict:
    core_contexts = _case_contexts(core_manifest)
    articles = {
        article["id"]: article
        for event in robustness_manifest["events"]
        for article in event["articles"]
    }
    rows = []
    for oracle_case in oracle["cases"]:
        context = core_contexts[oracle_case["case_id"]]
        evidence_articles = [
            articles[article_id] for article_id in oracle_case["evidence_article_ids"]
        ]
        batch = retrieve_pages(
            [_source(article) for article in evidence_articles],
            input_url=context["source_article"]["url"],
            settings=settings,
        )
        items = _evidence_items(batch.pages)
        selected = rank_passages(
            context["case"]["seed_claim"],
            [
                EvidencePassage(item.id, item.excerpt, item.publisher, item.cluster_id)
                for item in items
            ],
            local_models,
            limit=6,
        )
        similarities = (
            local_models.similarities(
                [context["case"]["seed_claim"]] * len(items),
                [item.excerpt for item in items],
            )
            if items
            else []
        )
        raw_rank = {
            item.id: rank
            for rank, (_, item) in enumerate(
                sorted(
                    zip(similarities, items, strict=True),
                    key=lambda pair: pair[0],
                    reverse=True,
                ),
                start=1,
            )
        }
        selected_ids = {result.passage.id for result in selected}
        page_by_article = _pages_by_article(batch.pages, evidence_articles)
        gold_results = []
        for gold in oracle_case["gold_passages"]:
            page = page_by_article.get(gold["article_id"])
            matching = [
                item
                for item in items
                if page is not None
                and canonicalize_url(str(item.url)) == canonicalize_url(page.url)
                and contains_quote(item.excerpt, gold["quote"])
            ]
            gold_results.append(
                {
                    "article_id": gold["article_id"],
                    "quote_sha256": sha256(gold["quote"].encode()).hexdigest(),
                    "page_readable": page is not None,
                    "gold_in_page": bool(page and contains_quote(page.text, gold["quote"])),
                    "gold_in_chunk": bool(matching),
                    "best_raw_rank": min(
                        (raw_rank[item.id] for item in matching),
                        default=None,
                    ),
                    "selected_top_six": any(item.id in selected_ids for item in matching),
                }
            )
        rows.append(
            {
                "case_id": oracle_case["case_id"],
                "source_language": oracle_case["source_language"],
                "topic": oracle_case["topic"],
                "match_policy": oracle_case["match_policy"],
                "retrieved_pages": len(batch.pages),
                "candidate_chunks": len(items),
                "retrieval_failures": len(batch.failures),
                "gold": gold_results,
                "failure_stage": _retrieval_failure_stage(
                    gold_results,
                    oracle_case["match_policy"],
                ),
            }
        )
    return {"cases": rows, "summary": summarize_holdout_diagnostics(rows)}


def summarize_holdout_diagnostics(rows: list[dict]) -> dict:
    denominator = len(rows)

    def passed(field: str) -> int:
        return sum(_gold_passes(row["gold"], field, row["match_policy"]) for row in rows)

    return {
        "cases": denominator,
        "stage_failures": dict(sorted(Counter(row["failure_stage"] for row in rows).items())),
        "extraction_recall": _rate(passed("gold_in_page"), denominator),
        "chunk_coverage": _rate(passed("gold_in_chunk"), denominator),
        "ranking_recall_at_six": _rate(passed("selected_top_six"), denominator),
    }


def summarize_diagnostics(rows: list[dict]) -> dict:
    answerable = [row for row in rows if row["answerability"] == "answerable"]
    denominator = len(answerable)

    def passed(field: str) -> int:
        return sum(any(item[field] for item in row["gold"]) for row in answerable)

    return {
        "cases": len(rows),
        "answerable_cases": denominator,
        "unanswerable_cases": sum(row["answerability"] == "unanswerable" for row in rows),
        "uncertain_cases": sum(row["answerability"] == "uncertain" for row in rows),
        "stage_failures": dict(sorted(Counter(row["failure_stage"] for row in rows).items())),
        "extraction_recall": _rate(passed("gold_in_page"), denominator),
        "chunk_coverage": _rate(passed("gold_in_chunk"), denominator),
        "ranking_recall_at_six": _rate(passed("selected_top_six"), denominator),
        "strict_aligned_recall": _rate(passed("strictly_aligned"), denominator),
        "aligned_or_partial_recall": _rate(
            passed("aligned_or_partial"),
            denominator,
        ),
    }


def _failure_stage(answerability: str, gold: list[dict]) -> str:
    if answerability != "answerable":
        return "not_applicable"
    if not any(item["page_readable"] for item in gold):
        return "extraction"
    if not any(item["gold_in_page"] for item in gold):
        return "source_changed_or_oracle_mismatch"
    if not any(item["gold_in_chunk"] for item in gold):
        return "chunking"
    if not any(item["selected_top_six"] for item in gold):
        return "ranking"
    if any(item["strictly_aligned"] for item in gold):
        return "passed"
    if any(item["aligned_or_partial"] for item in gold):
        return "partial_alignment"
    if not any(item["aligned_or_partial"] for item in gold):
        return "alignment"
    raise AssertionError("Unhandled alignment state.")


def _retrieval_failure_stage(gold: list[dict], match_policy: str) -> str:
    if not _gold_passes(gold, "page_readable", match_policy):
        return "extraction"
    if not _gold_passes(gold, "gold_in_page", match_policy):
        return "source_changed_or_oracle_mismatch"
    if not _gold_passes(gold, "gold_in_chunk", match_policy):
        return "chunking"
    if not _gold_passes(gold, "selected_top_six", match_policy):
        return "ranking"
    return "passed"


def _gold_passes(gold: list[dict], field: str, match_policy: str) -> bool:
    outcomes = [bool(item[field]) for item in gold]
    return all(outcomes) if match_policy == "all" else any(outcomes)


def _rate(numerator: int, denominator: int) -> dict:
    return {
        "passed": numerator,
        "eligible": denominator,
        "rate": round(numerator / denominator, 4) if denominator else None,
    }


def _case_contexts(manifest: dict) -> dict[str, dict]:
    contexts = {}
    for event in manifest["events"]:
        for case in event["trace_cases"]:
            source_article = next(
                article
                for article in event["articles"]
                if article["source_language"] == case["seed_language"]
                and article.get("selection", "frozen_core") == "frozen_core"
            )
            comparison = [
                article
                for article in event["articles"]
                if article["id"] != source_article["id"]
                and article.get("selection", "frozen_core") == "frozen_core"
            ]
            contexts[case["id"]] = {
                "case": case,
                "event": event,
                "source_article": source_article,
                "comparison_articles": comparison,
                "comparison_ids": [article["id"] for article in comparison],
            }
    return contexts


def _source(article: dict) -> DiscoveredSource:
    return DiscoveredSource(
        url=article["url"],
        title=article["title"],
        publisher=article["publisher"],
        language=Language(article["source_language"]),
        source_type=SourceType.WEB,
        discovery_method=DiscoveryMethod.GOOGLE_SEARCH,
    )


def _pages_by_article(pages, articles: list[dict]) -> dict[str, object]:
    article_by_url = {canonicalize_url(article["url"]): article["id"] for article in articles}
    return {
        article_by_url[canonicalize_url(page.source.url)]: page
        for page in pages
        if canonicalize_url(page.source.url) in article_by_url
    }
