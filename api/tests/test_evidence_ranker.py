from app.evidence_ranker import EvidencePassage, chunk_text, rank_passages
from app.models import Language


class FakeLocalModels:
    def similarities(self, left, right):
        del left
        return [float(text.rsplit(" ", 1)[-1]) for text in right]


def test_chunker_keeps_normal_article_passages_bounded() -> None:
    sentence = "A concise sentence contains exactly six words."
    text = " ".join(f"{sentence[:-1]} {index}." for index in range(80))

    chunks = chunk_text(text, Language.ENGLISH)
    word_counts = [len(chunk.split()) for chunk in chunks]

    assert len(chunks) > 1
    assert all(count <= 220 for count in word_counts)
    assert all(count >= 120 for count in word_counts[:-1])


def test_ranker_deduplicates_clusters_and_limits_publishers() -> None:
    passages = [
        EvidencePassage("a", "score 0.99", "Wire A", "same-wire"),
        EvidencePassage("b", "score 0.98", "Outlet B", "same-wire"),
        EvidencePassage("c", "score 0.97", "Wire A", "different"),
        EvidencePassage("d", "score 0.96", "Wire A", "third"),
        EvidencePassage("e", "score 0.95", "Outlet C", "fourth"),
    ]

    ranked = rank_passages(
        "claim",
        passages,
        FakeLocalModels(),
        limit=4,
        per_publisher=2,
    )

    assert [item.passage.id for item in ranked] == ["a", "c", "e"]
    assert len({item.passage.cluster_id for item in ranked}) == len(ranked)
