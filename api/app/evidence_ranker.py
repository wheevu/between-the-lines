from dataclasses import dataclass

from app.local_models import LocalModels
from app.models import Language
from app.segmentation import segment_article


@dataclass(frozen=True)
class EvidencePassage:
    id: str
    text: str
    publisher: str
    cluster_id: str


@dataclass(frozen=True)
class RankedPassage:
    passage: EvidencePassage
    relevance: float


def chunk_text(
    text: str,
    language: Language,
    *,
    target_words: int = 170,
    max_words: int = 220,
) -> list[str]:
    sentences = [segment.text for segment in segment_article(text, language)]
    chunks: list[list[str]] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and (
            current_words >= target_words or current_words + sentence_words > max_words
        ):
            chunks.append(current)
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words

    if current:
        if chunks and sum(len(item.split()) for item in current) < 120:
            previous_words = sum(len(item.split()) for item in chunks[-1])
            if previous_words + current_words <= max_words:
                chunks[-1].extend(current)
            else:
                chunks.append(current)
        else:
            chunks.append(current)
    return [" ".join(chunk) for chunk in chunks]


def rank_passages(
    claim: str,
    passages: list[EvidencePassage],
    local_models: LocalModels,
    *,
    limit: int = 5,
    per_publisher: int = 2,
) -> list[RankedPassage]:
    if not passages or limit <= 0:
        return []
    similarities = local_models.similarities(
        [claim] * len(passages),
        [passage.text for passage in passages],
    )
    scored = sorted(
        (
            RankedPassage(passage=passage, relevance=similarity)
            for passage, similarity in zip(passages, similarities, strict=True)
        ),
        key=lambda item: item.relevance,
        reverse=True,
    )

    selected: list[RankedPassage] = []
    publisher_counts: dict[str, int] = {}
    clusters: set[str] = set()
    for item in scored:
        publisher = item.passage.publisher
        if publisher_counts.get(publisher, 0) >= per_publisher:
            continue
        if item.passage.cluster_id in clusters:
            continue
        selected.append(item)
        publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
        clusters.add(item.passage.cluster_id)
        if len(selected) == limit:
            break
    return selected
