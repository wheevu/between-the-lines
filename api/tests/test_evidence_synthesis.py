from types import SimpleNamespace

import pytest

from app.evidence_synthesis import (
    EvidenceClassifier,
    EvidenceSynthesisError,
    _stance_prompt,
    assess_claim,
)
from app.models import (
    AlignmentState,
    ClaimCandidate,
    ClaimEvidenceStatus,
    ClaimType,
    EvidenceItem,
    EvidenceSourceKind,
    EvidenceStance,
    GeminiEvidenceStance,
    GeminiStanceBatch,
    Language,
)


def claim(claim_type: ClaimType = ClaimType.FACT) -> ClaimCandidate:
    return ClaimCandidate(
        id="claim-1",
        source_quote="The agency reported 24 buses.",
        segment_ids=["p1s1"],
        standalone_claim="The agency reported 24 buses.",
        claim_type=claim_type,
        numbers=["24"],
        reason="A specific number.",
    )


def evidence(
    identifier: str,
    *,
    cluster: str,
    stance: EvidenceStance | None,
    source_type: EvidenceSourceKind = EvidenceSourceKind.DIRECT_REPORTING,
    direct: bool = False,
) -> EvidenceItem:
    return EvidenceItem(
        id=identifier,
        url=f"https://{identifier}.example/report",
        publisher=f"{identifier}.example",
        language=Language.ENGLISH,
        excerpt=f"Evidence excerpt {identifier}.",
        source_type=source_type,
        content_hash=f"hash-{identifier}",
        cluster_id=cluster,
        relevance=0.9,
        stance=stance,
        stance_reason="A test relationship." if stance else None,
        direct=direct if stance else None,
    )


def test_two_independent_supporting_clusters_are_supported() -> None:
    assessment = assess_claim(
        claim(),
        [
            evidence("e1", cluster="one", stance=EvidenceStance.SUPPORTS),
            evidence("e2", cluster="two", stance=EvidenceStance.SUPPORTS),
        ],
    )

    assert assessment.status is ClaimEvidenceStatus.SUPPORTED
    assert assessment.support_evidence_ids == ["e1", "e2"]
    assert assessment.explanation == (
        "At least two independent sources support this claim. "
        "No equally strong contradiction was found."
    )
    assert any(
        "uncredited or undetected reuse" in limitation for limitation in assessment.limitations
    )


def test_one_model_classified_primary_source_cannot_bypass_independence_rule() -> None:
    assessment = assess_claim(
        claim(),
        [
            evidence(
                "primary",
                cluster="one",
                stance=EvidenceStance.SUPPORTS,
                source_type=EvidenceSourceKind.PRIMARY,
                direct=True,
            )
        ],
    )

    assert assessment.status is ClaimEvidenceStatus.INSUFFICIENT


def test_two_clusters_from_one_publisher_are_not_independent() -> None:
    first = evidence("one", cluster="one", stance=EvidenceStance.SUPPORTS)
    second = evidence("two", cluster="two", stance=EvidenceStance.SUPPORTS)

    assessment = assess_claim(
        claim(),
        [
            first.model_copy(update={"publisher": "Same desk", "publisher_key": "same.example"}),
            second.model_copy(update={"publisher": "Same desk", "publisher_key": "same.example"}),
        ],
    )

    assert assessment.status is ClaimEvidenceStatus.INSUFFICIENT
    assert any("distinct publishers" in item for item in assessment.limitations)


def test_repeated_wire_cluster_is_not_independent_confirmation() -> None:
    assessment = assess_claim(
        claim(),
        [
            evidence("wire", cluster="same", stance=EvidenceStance.SUPPORTS),
            evidence("copy", cluster="same", stance=EvidenceStance.SUPPORTS),
        ],
    )

    assert assessment.status is ClaimEvidenceStatus.INSUFFICIENT
    assert any(
        "repeat the same original report" in limitation for limitation in assessment.limitations
    )


def test_strong_support_and_dispute_are_mixed() -> None:
    assessment = assess_claim(
        claim(),
        [
            evidence("s1", cluster="support-1", stance=EvidenceStance.SUPPORTS),
            evidence("s2", cluster="support-2", stance=EvidenceStance.SUPPORTS),
            evidence("d1", cluster="dispute-1", stance=EvidenceStance.DISPUTES),
            evidence("d2", cluster="dispute-2", stance=EvidenceStance.DISPUTES),
        ],
    )

    assert assessment.status is ClaimEvidenceStatus.MIXED
    assert "at least two challenge it" in assessment.explanation


def test_attributed_claim_never_implies_the_allegation_was_proved() -> None:
    assessment = assess_claim(
        claim(ClaimType.ATTRIBUTED),
        [
            evidence(
                "statement",
                cluster="primary",
                stance=EvidenceStance.SUPPORTS,
                source_type=EvidenceSourceKind.PRIMARY,
                direct=True,
            ),
            evidence(
                "report",
                cluster="independent-report",
                stance=EvidenceStance.SUPPORTS,
            ),
        ],
    )

    assert assessment.status is ClaimEvidenceStatus.SUPPORTED
    assert any("statement was made" in limitation for limitation in assessment.limitations)


class FakeModels:
    def __init__(self, batch: GeminiStanceBatch) -> None:
        self.batch = batch

    def generate_content(self, **kwargs):
        del kwargs
        return SimpleNamespace(parsed=self.batch)


def test_classifier_rejects_changed_evidence_identifiers() -> None:
    classifier = EvidenceClassifier("key", "model")
    classifier.client = SimpleNamespace(
        models=FakeModels(
            GeminiStanceBatch(
                evidence=[
                    GeminiEvidenceStance(
                        evidence_id="invented",
                        stance=EvidenceStance.SUPPORTS,
                        reason="Invented.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                    )
                ]
            )
        )
    )

    with pytest.raises(EvidenceSynthesisError, match="changed or omitted"):
        classifier.classify(
            claim(),
            [evidence("real", cluster="one", stance=None)],
        )


def test_stance_prompt_marks_claim_and_excerpts_as_untrusted() -> None:
    dated = evidence("e1", cluster="one", stance=None).model_copy(
        update={"published_at": "2026-03-08"}
    )
    prompt = _stance_prompt(
        claim(),
        [dated],
    )

    assert "untrusted document content" in prompt
    assert "do not use outside" in prompt.lower()
    assert "does not mean an allegation" in prompt
    assert '"published_at": "2026-03-08"' in prompt
    assert "appearing in a photo" in prompt
    assert 'relative dates such as "last month"' in prompt
    assert "unverified page metadata" in prompt
    assert "excerpt itself corroborates the date" in prompt
    assert "filed complaint, ruling, and final finding" in prompt
    assert "source trail" not in prompt
    assert "credited_origin" in prompt


def test_classifier_downgrades_only_an_unanchored_aligned_quote() -> None:
    classifier = EvidenceClassifier("key", "model")
    classifier.client = SimpleNamespace(
        models=FakeModels(
            GeminiStanceBatch(
                evidence=[
                    GeminiEvidenceStance(
                        evidence_id="real",
                        stance=EvidenceStance.SUPPORTS,
                        reason="The same figure appears.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                        aligned_quote="A quotation the source never contained.",
                        alignment_state=AlignmentState.ALIGNED,
                    ),
                    GeminiEvidenceStance(
                        evidence_id="valid",
                        stance=EvidenceStance.SUPPORTS,
                        reason="The exact excerpt is aligned.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                        aligned_quote="Evidence excerpt valid.",
                        alignment_state=AlignmentState.ALIGNED,
                    ),
                ]
            )
        )
    )

    classified = classifier.classify(
        claim(),
        [
            evidence("real", cluster="one", stance=None),
            evidence("valid", cluster="two", stance=None),
        ],
    )

    assert classified[0].stance is EvidenceStance.CONTEXT
    assert classified[0].alignment_state is AlignmentState.UNCERTAIN
    assert classified[0].aligned_quote is None
    assert "literal aligned quote" in classified[0].mismatch
    assert classified[1].stance is EvidenceStance.SUPPORTS
    assert classified[1].aligned_quote == "Evidence excerpt valid."


def test_classifier_recovers_exact_sentence_after_punctuation_only_quote_drift() -> None:
    classifier = EvidenceClassifier("key", "model")
    classifier.client = SimpleNamespace(
        models=FakeModels(
            GeminiStanceBatch(
                evidence=[
                    GeminiEvidenceStance(
                        evidence_id="real",
                        stance=EvidenceStance.SUPPORTS,
                        reason="The same figure appears.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                        aligned_quote="Evidence, excerpt real.",
                        alignment_state=AlignmentState.ALIGNED,
                    )
                ]
            )
        )
    )

    classified = classifier.classify(
        claim(),
        [evidence("real", cluster="one", stance=None)],
    )

    assert classified[0].stance is EvidenceStance.SUPPORTS
    assert classified[0].alignment_state is AlignmentState.ALIGNED
    assert classified[0].aligned_quote == "Evidence excerpt real."


def test_classifier_keeps_only_origins_named_in_the_exact_excerpt() -> None:
    classifier = EvidenceClassifier("key", "model")
    classifier.client = SimpleNamespace(
        models=FakeModels(
            GeminiStanceBatch(
                evidence=[
                    GeminiEvidenceStance(
                        evidence_id="grounded",
                        stance=EvidenceStance.CONTEXT,
                        reason="The excerpt explicitly credits Reuters.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                        credited_origin="Reuters",
                    ),
                    GeminiEvidenceStance(
                        evidence_id="ungrounded",
                        stance=EvidenceStance.CONTEXT,
                        reason="The model supplied an unsupported origin.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                        credited_origin="Reuters",
                    ),
                    GeminiEvidenceStance(
                        evidence_id="short-origin",
                        stance=EvidenceStance.CONTEXT,
                        reason="A short source name only occurs inside another word.",
                        direct=False,
                        source_type=EvidenceSourceKind.DIRECT_REPORTING,
                        credited_origin="AP",
                    ),
                ]
            )
        )
    )
    grounded = evidence("grounded", cluster="one", stance=None).model_copy(
        update={"excerpt": "Reuters reported the figure on Tuesday."}
    )
    ungrounded = evidence("ungrounded", cluster="two", stance=None)
    short_origin = evidence("short-origin", cluster="three", stance=None).model_copy(
        update={"excerpt": "The device is capable of running locally."}
    )

    classified = classifier.classify(claim(), [grounded, ungrounded, short_origin])

    assert classified[0].credited_origin == "Reuters"
    assert classified[1].credited_origin is None
    assert classified[2].credited_origin is None
