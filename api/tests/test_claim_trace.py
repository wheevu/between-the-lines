from app.claim_trace import assign_source_lineages, build_trace_summary
from app.models import (
    ClaimAssessment,
    ClaimEvidenceStatus,
    EvidenceItem,
    EvidenceSourceKind,
    EvidenceStance,
    Language,
    MeaningDelta,
    MeaningDeltaType,
    TraceEvidenceState,
)


class FakeLocalModels:
    def similarities(self, left, right):
        return [
            0.98 if "Reuters" in first and "로이터" in second else 0.3
            for first, second in zip(left, right, strict=True)
        ]


def evidence(
    identifier: str,
    *,
    language: Language,
    origin: str | None,
    cluster: str,
) -> EvidenceItem:
    return EvidenceItem(
        id=identifier,
        url=f"https://{identifier}.example/report",
        publisher=f"Publisher {identifier}",
        publisher_key=f"{identifier}.example",
        language=language,
        excerpt=f"Evidence {identifier}.",
        source_type=EvidenceSourceKind.DIRECT_REPORTING,
        content_hash=f"hash-{identifier}",
        cluster_id=cluster,
        relevance=0.9,
        stance=EvidenceStance.SUPPORTS,
        credited_origin=origin,
    )


def test_cross_language_reports_with_the_same_credited_origin_share_a_lineage() -> None:
    assigned = assign_source_lineages(
        [
            evidence(
                "english",
                language=Language.ENGLISH,
                origin="Reuters",
                cluster="english-copy",
            ),
            evidence(
                "korean",
                language=Language.KOREAN,
                origin="로이터",
                cluster="korean-copy",
            ),
            evidence(
                "vietnamese",
                language=Language.VIETNAMESE,
                origin=None,
                cluster="independent",
            ),
        ],
        FakeLocalModels(),
    )

    assert assigned[0].cluster_id == assigned[1].cluster_id
    assert assigned[2].cluster_id == "independent"


def test_credited_lineage_applies_to_every_passage_from_the_same_article() -> None:
    credited = evidence(
        "credited",
        language=Language.ENGLISH,
        origin="Reuters",
        cluster="credited-passage",
    )
    uncredited = evidence(
        "uncredited",
        language=Language.ENGLISH,
        origin=None,
        cluster="another-passage",
    ).model_copy(update={"url": credited.url})

    assigned = assign_source_lineages([credited, uncredited], FakeLocalModels())

    assert assigned[0].cluster_id.startswith("lineage-")
    assert assigned[1].cluster_id == assigned[0].cluster_id


def test_literal_acronym_bridges_credited_origins_across_scripts() -> None:
    assigned = assign_source_lineages(
        [
            evidence(
                "english",
                language=Language.ENGLISH,
                origin="World Meteorological Organization",
                cluster="english-copy",
            ),
            evidence(
                "korean",
                language=Language.KOREAN,
                origin="세계기상기구(WMO)",
                cluster="korean-copy",
            ),
        ],
        FakeLocalModels(),
    )

    assert assigned[0].cluster_id == assigned[1].cluster_id


def test_trace_summary_keeps_language_deltas_separate_from_evidence_state() -> None:
    first = evidence(
        "english",
        language=Language.ENGLISH,
        origin=None,
        cluster="one",
    ).model_copy(
        update={
            "meaning_deltas": [
                MeaningDelta(
                    type=MeaningDeltaType.CERTAINTY,
                    description="The English report says expected rather than confirmed.",
                )
            ]
        }
    )
    second = evidence(
        "vietnamese",
        language=Language.VIETNAMESE,
        origin=None,
        cluster="two",
    )
    assessment = ClaimAssessment(
        claim_id="claim-1",
        status=ClaimEvidenceStatus.SUPPORTED,
        explanation="Two independent sources support the claim.",
        support_evidence_ids=["english", "vietnamese"],
    )

    trace = build_trace_summary(assessment, [first, second])

    assert trace.evidence_state is TraceEvidenceState.CORROBORATED
    assert trace.independent_lineages == 2
    assert trace.languages == [Language.ENGLISH, Language.VIETNAMESE]
    assert trace.meaning_deltas[0].type is MeaningDeltaType.CERTAINTY


def test_trace_summary_counts_articles_not_passage_clusters_as_lineages() -> None:
    first = evidence(
        "first-passage",
        language=Language.ENGLISH,
        origin=None,
        cluster="passage-one",
    )
    second = evidence(
        "second-passage",
        language=Language.ENGLISH,
        origin=None,
        cluster="passage-two",
    ).model_copy(update={"url": first.url})
    assessment = ClaimAssessment(
        claim_id="claim-1",
        status=ClaimEvidenceStatus.INSUFFICIENT,
        explanation="One article is not independent corroboration.",
    )

    trace = build_trace_summary(assessment, [first, second])

    assert trace.article_count == 1
    assert trace.independent_lineages == 1


def test_trace_summary_merges_distinct_articles_with_one_credited_lineage() -> None:
    shared_lineage = "lineage-shared"
    assessment = ClaimAssessment(
        claim_id="claim-1",
        status=ClaimEvidenceStatus.INSUFFICIENT,
        explanation="Two articles repeat one credited source.",
    )

    trace = build_trace_summary(
        assessment,
        [
            evidence(
                "english",
                language=Language.ENGLISH,
                origin="Reuters",
                cluster=shared_lineage,
            ),
            evidence(
                "korean",
                language=Language.KOREAN,
                origin="로이터",
                cluster=shared_lineage,
            ),
        ],
    )

    assert trace.article_count == 2
    assert trace.independent_lineages == 1
