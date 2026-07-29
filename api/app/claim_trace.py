import re
import unicodedata
from hashlib import sha256
from itertools import combinations

from app.local_models import LocalModels
from app.models import (
    ClaimAssessment,
    ClaimEvidenceStatus,
    ClaimTraceSummary,
    EvidenceItem,
    EvidenceStance,
    Language,
    MeaningDelta,
    TraceEvidenceState,
)

WHITESPACE = re.compile(r"\s+")
UPPERCASE_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
LATIN_WORD = re.compile(r"[A-Za-z]+")
ORIGIN_SIMILARITY_THRESHOLD = 0.94


def assign_source_lineages(
    evidence: list[EvidenceItem],
    local_models: LocalModels,
) -> list[EvidenceItem]:
    with_origin = [(index, item) for index, item in enumerate(evidence) if item.credited_origin]
    if not with_origin:
        return evidence

    parents = list(range(len(with_origin)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = root(left)
        right_root = root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    pairs = list(combinations(range(len(with_origin)), 2))
    if pairs:
        left = [with_origin[a][1].credited_origin or "" for a, _ in pairs]
        right = [with_origin[b][1].credited_origin or "" for _, b in pairs]
        try:
            similarities = local_models.similarities(left, right)
        except Exception:
            similarities = [0.0] * len(pairs)
        for (first, second), similarity in zip(pairs, similarities, strict=True):
            first_origin = with_origin[first][1].credited_origin or ""
            second_origin = with_origin[second][1].credited_origin or ""
            if (
                _normalize(first_origin) == _normalize(second_origin)
                or _origin_aliases(first_origin) & _origin_aliases(second_origin)
                or similarity >= ORIGIN_SIMILARITY_THRESHOLD
            ):
                union(first, second)

    origins_by_root: dict[int, list[str]] = {}
    for index, (_, item) in enumerate(with_origin):
        origins_by_root.setdefault(root(index), []).append(item.credited_origin or "")
    lineage_by_root = {
        group: f"lineage-{sha256('|'.join(sorted(origins)).encode()).hexdigest()[:12]}"
        for group, origins in origins_by_root.items()
    }
    lineage_by_evidence_index = {
        evidence_index: lineage_by_root[root(index)]
        for index, (evidence_index, _) in enumerate(with_origin)
    }
    assigned = [
        item.model_copy(
            update={"cluster_id": lineage_by_evidence_index.get(index, item.cluster_id)}
        )
        for index, item in enumerate(evidence)
    ]
    lineage_by_url: dict[str, str] = {}
    for item in assigned:
        if item.cluster_id.startswith("lineage-"):
            url = str(item.url)
            lineage_by_url[url] = min(
                item.cluster_id,
                lineage_by_url.get(url, item.cluster_id),
            )
    return [
        item.model_copy(update={"cluster_id": lineage_by_url.get(str(item.url), item.cluster_id)})
        for item in assigned
    ]


def build_trace_summary(
    assessment: ClaimAssessment,
    evidence: list[EvidenceItem],
) -> ClaimTraceSummary:
    relevant = [
        item
        for item in evidence
        if item.stance is not None and item.stance is not EvidenceStance.IRRELEVANT
    ]
    deltas: list[MeaningDelta] = []
    seen_deltas: set[tuple[str, str]] = set()
    for item in relevant:
        for delta in item.meaning_deltas:
            identity = (delta.type.value, _normalize(delta.description))
            if identity not in seen_deltas:
                seen_deltas.add(identity)
                deltas.append(delta)

    state = {
        ClaimEvidenceStatus.SUPPORTED: TraceEvidenceState.CORROBORATED,
        ClaimEvidenceStatus.DISPUTED: TraceEvidenceState.CONFLICTING,
        ClaimEvidenceStatus.MIXED: TraceEvidenceState.CONFLICTING,
        ClaimEvidenceStatus.INSUFFICIENT: TraceEvidenceState.UNRESOLVED,
    }[assessment.status]
    languages = sorted(
        {item.language for item in relevant},
        key=lambda language: list(Language).index(language),
    )
    return ClaimTraceSummary(
        evidence_state=state,
        article_count=len({item.url for item in relevant}),
        independent_lineages=len(_article_lineage_keys(relevant)),
        languages=languages,
        meaning_deltas=deltas,
    )


def _article_lineage_keys(evidence: list[EvidenceItem]) -> set[str]:
    by_url: dict[str, list[EvidenceItem]] = {}
    for item in evidence:
        by_url.setdefault(str(item.url), []).append(item)

    lineages = set()
    for url, items in by_url.items():
        credited_lineages = sorted(
            {item.cluster_id for item in items if item.cluster_id.startswith("lineage-")}
        )
        lineages.add(
            credited_lineages[0]
            if credited_lineages
            else f"article-{sha256(url.encode()).hexdigest()[:12]}"
        )
    return lineages


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return WHITESPACE.sub(" ", normalized).strip()


def _origin_aliases(value: str) -> set[str]:
    aliases = {match.group(0) for match in UPPERCASE_ACRONYM.finditer(value)}
    latin_words = LATIN_WORD.findall(value)
    if len(latin_words) >= 2:
        aliases.add("".join(word[0] for word in latin_words).upper())
    return aliases
