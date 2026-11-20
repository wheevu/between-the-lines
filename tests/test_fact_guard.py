"""Tests for deterministic EN/VI/KO translation verification and fact-drift checks."""

from __future__ import annotations

import pytest

from btl.fact_guard import anchor_quote, audit_translations, check_translation_pair
from btl.types import DriftCategory, Language, TranslationPairInput


def test_number_change_flagged_high_confidence() -> None:
    res = check_translation_pair(
        TranslationPairInput(
            source_text="The plan covers 12 provinces.",
            translation_text="Kế hoạch áp dụng trên 21 tỉnh.",
            source_language="en",
            target_language="vi",
        )
    )
    assert res.status == "drift_detected"
    assert [f.category for f in res.flags] == [DriftCategory.NUMBER]
    assert res.flags[0].confidence == "high"


@pytest.mark.parametrize(
    ("src", "tgt", "sl", "tl"),
    [
        (
            "8 bài đăng vượt 9,5 triệu lượt thích và 100.000 bình luận.",
            "8 posts exceeded 9.5 million likes and 100,000 comments.",
            "vi",
            "en",
        ),
        (
            "8 bài đăng vượt 9,5 triệu lượt thích và 100.000 bình luận.",
            "게시물 8개가 좋아요 950만 개와 댓글 10만 개를 넘겼다.",
            "vi",
            "ko",
        ),
        (
            "예산은 4월에 1억 5000만 원에 달했다.",
            "Ngân sách đạt 150 triệu won vào tháng 4.",
            "ko",
            "vi",
        ),
        (
            "The program may begin in September.",
            "Chương trình có thể bắt đầu vào tháng 9.",
            "en",
            "vi",
        ),
        (
            "Thứ Hai, ngày 27 tháng 4, văn phòng mở cửa.",
            "On Monday, April 27, the office opened.",
            "vi",
            "en",
        ),
    ],
)
def test_cross_lingual_numbers_and_dates_match_without_false_positives(
    src: str, tgt: str, sl: str, tl: str
) -> None:
    res = check_translation_pair(
        TranslationPairInput(
            source_text=src,
            translation_text=tgt,
            source_language=sl,  # type: ignore[arg-type]
            target_language=tl,  # type: ignore[arg-type]
        )
    )
    assert not any(f.category is DriftCategory.NUMBER for f in res.flags)


def test_negation_drop_flagged_and_false_positives_guarded() -> None:
    dropped = check_translation_pair(
        TranslationPairInput(
            source_text="The minister did not confirm the date.",
            translation_text="장관은 날짜를 확정했습니다.",
        )
    )
    assert DriftCategory.NEGATION in [f.category for f in dropped.flags]

    litotes = check_translation_pair(
        TranslationPairInput(
            source_text="Không ít khán giả bày tỏ sự mệt mỏi.",
            translation_text="피로감을 표하는 대중도 적지 않다.",
        )
    )
    assert not any(f.category is DriftCategory.NEGATION for f in litotes.flags)

    question = check_translation_pair(
        TranslationPairInput(
            source_text="Liệu đề xuất có được thông qua hay không.",
            translation_text="Whether the proposal will pass.",
        )
    )
    assert not any(f.category is DriftCategory.NEGATION for f in question.flags)


def test_modality_shift_and_legal_state_elevation_and_attribution_loss() -> None:
    # Korean allegation + hearsay dropped into assertive English ruling/fact
    res = check_translation_pair(
        TranslationPairInput(
            source_text="보도에 따르면 경찰은 관련 혐의를 수사 중이며 벌금이 부과될 수 있다.",
            translation_text="Police found the company guilty and imposed a fine.",
            source_language="ko",
            target_language="en",
        )
    )
    cats = {f.category for f in res.flags}
    assert DriftCategory.MODALITY_SHIFT in cats
    assert DriftCategory.LEGAL_STATE_SHIFT in cats
    assert DriftCategory.ATTRIBUTION_LOSS in cats


def test_vietnamese_attribution_preserved_does_not_false_positive() -> None:
    res = check_translation_pair(
        TranslationPairInput(
            source_text="According to Reuters, the bill passed in 2026.",
            translation_text="Theo Reuters, dự luật đã được thông qua năm 2026.",
        )
    )
    assert res.status == "clean"
    assert res.source_language is Language.ENGLISH
    assert res.target_language is Language.VIETNAMESE


def test_unanchored_quote_detected_and_normalized_quote_anchored() -> None:
    anchored = anchor_quote(
        "The budget rose 12 percent",
        "Official notice: The budget rose 12 percent! All districts comply.",
    )
    assert anchored is not None

    res = audit_translations(
        [
            TranslationPairInput(
                source_text="The ministry published Decree 15.",
                translation_text="Bộ đã ban hành Nghị định 15.",
                source_quote="nonexistent phrase",
            )
        ]
    )
    assert res.status == "drift_detected"
    assert res.flagged_count == 1
    assert res.pairs[0].flags[0].category is DriftCategory.UNANCHORED_QUOTE
