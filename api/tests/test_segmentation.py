import pytest

from app.models import Language
from app.segmentation import normalize_article, segment_article


@pytest.mark.parametrize(
    ("language", "text"),
    [
        (Language.ENGLISH, "First sentence. Second sentence?"),
        (Language.VIETNAMESE, "Câu thứ nhất. Câu thứ hai?"),
        (Language.KOREAN, "첫 번째 문장입니다. 두 번째 문장인가요?"),
    ],
)
def test_segment_article_preserves_order_and_assigns_stable_ids(
    language: Language, text: str
) -> None:
    segments = segment_article(text, language)

    assert [segment.id for segment in segments] == ["p1s1", "p1s2"]
    assert " ".join(segment.text for segment in segments) == text


def test_segment_article_preserves_paragraph_boundaries() -> None:
    segments = segment_article("First.\n\nSecond.", Language.ENGLISH)

    assert [(segment.id, segment.paragraph_index) for segment in segments] == [
        ("p1s1", 0),
        ("p2s1", 1),
    ]


def test_normalize_article_collapses_noise_without_joining_paragraphs() -> None:
    assert normalize_article("  One   line. \r\n\r\n Two\tline. ") == "One line.\n\nTwo line."


def test_normalize_article_removes_paste_ui_artifacts_and_adjacent_duplicates() -> None:
    text = "Headline\n\u200b\n Summarize \n\u200b\nHeadline\nBody.\nPhoto: Lotte\nPhoto: Lotte"

    assert normalize_article(text) == "Headline\n\nBody.\n\nPhoto: Lotte"


def test_normalize_article_removes_short_korean_copyright_footer() -> None:
    text = (
        "기사 본문입니다.\n"
        "※ 이 콘텐츠는 저작권법에 의하여 보호를 받는바, 무단 전재 복제, "
        "배포 및 이용(AI학습 포함)등을 금합니다."
    )

    assert normalize_article(text) == "기사 본문입니다."


def test_number_abbreviation_does_not_split_a_sentence() -> None:
    segments = segment_article(
        "The group reached No. 1 on Billboard 200. Its next song followed.",
        Language.ENGLISH,
    )

    assert [segment.text for segment in segments] == [
        "The group reached No. 1 on Billboard 200.",
        "Its next song followed.",
    ]


def test_dotted_country_abbreviation_does_not_break_legal_name() -> None:
    segments = segment_article(
        (
            "A publisher filed suit with the U.S. District Court on Tuesday. "
            "The company requested damages."
        ),
        Language.ENGLISH,
    )

    assert [segment.text for segment in segments] == [
        "A publisher filed suit with the U.S. District Court on Tuesday.",
        "The company requested damages.",
    ]


def test_dotted_country_abbreviation_can_still_end_a_sentence() -> None:
    segments = segment_article(
        "The product is available in the U.S. Sales begin next month.",
        Language.ENGLISH,
    )

    assert [segment.text for segment in segments] == [
        "The product is available in the U.S.",
        "Sales begin next month.",
    ]
