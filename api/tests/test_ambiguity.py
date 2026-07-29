import pytest

from app.ambiguity import build_flags
from app.models import (
    AmbiguityCategory,
    FlagKind,
    GeminiNote,
    Language,
)


def test_number_change_is_a_high_confidence_meaning_risk() -> None:
    flags = build_flags(
        source_text="The plan covers 12 provinces.",
        primary_text="Kế hoạch áp dụng trên 21 tỉnh.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert len(flags) == 1
    assert flags[0].category is AmbiguityCategory.NUMBER
    assert flags[0].kind is FlagKind.MEANING_RISK
    assert flags[0].confidence == "high"


def test_translated_units_do_not_create_a_number_mismatch() -> None:
    flags = build_flags(
        source_text="The program covers 12 provinces.",
        primary_text="Chương trình bao phủ 12 tỉnh.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert flags == []


def test_named_month_and_numeric_month_are_equivalent() -> None:
    flags = build_flags(
        source_text="The program may begin in September.",
        primary_text="Chương trình có thể bắt đầu vào tháng 9.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert flags == []


def test_negation_change_is_detected_across_languages() -> None:
    flags = build_flags(
        source_text="The minister did not confirm the date.",
        primary_text="장관은 날짜를 확정했습니다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.94,
        back_translation_similarity=None,
    )

    assert [flag.category for flag in flags] == [AmbiguityCategory.NEGATION]
    assert flags[0].confidence == "medium"


def test_locale_and_scale_formatted_numbers_match_vietnamese_to_english() -> None:
    flags = build_flags(
        source_text="8 bài đăng vượt 9,5 triệu lượt thích và 100.000 bình luận.",
        primary_text="8 posts exceeded 9.5 million likes and 100,000 comments.",
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_locale_and_scale_formatted_numbers_match_vietnamese_to_korean() -> None:
    flags = build_flags(
        source_text="8 bài đăng vượt 9,5 triệu lượt thích và 100.000 bình luận.",
        primary_text="게시물 8개가 좋아요 950만 개와 댓글 10만 개를 넘겼다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_three_digit_decimal_is_not_mistaken_for_a_grouping_separator() -> None:
    flags = build_flags(
        source_text="The audience reached 1.234 million.",
        primary_text="관객 수는 123.4만 명에 달했다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_vietnamese_litotes_matches_positive_english_equivalent() -> None:
    flags = build_flags(
        source_text="Không ít khán giả bày tỏ sự mệt mỏi.",
        primary_text="Quite a few viewers expressed fatigue.",
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_vietnamese_absence_matches_korean_omission_equivalent() -> None:
    flags = build_flags(
        source_text="Đội hình không có Danielle.",
        primary_text="다니엘이 빠진 구성이다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_vietnamese_hay_khong_matches_english_whether() -> None:
    flags = build_flags(
        source_text="Liệu màn tái xuất có thành công hay không.",
        primary_text="Whether the comeback succeeds.",
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_vietnamese_except_matches_korean_exclusion() -> None:
    flags = build_flags(
        source_text="Đội hình bốn thành viên, ngoại trừ Danielle.",
        primary_text="다니엘을 제외한 4인조 구성이다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_vietnamese_except_matches_english_exclusion() -> None:
    flags = build_flags(
        source_text="Đội hình bốn thành viên, ngoại trừ Danielle.",
        primary_text="A four-member lineup, excluding Danielle.",
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_vietnamese_litotes_matches_korean_litotes() -> None:
    flags = build_flags(
        source_text="Không ít khán giả bày tỏ sự mệt mỏi.",
        primary_text="피로감을 표하는 대중도 적지 않다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_korean_or_is_not_treated_as_negation() -> None:
    flags = build_flags(
        source_text="It will keep its style or introduce something new.",
        primary_text="기존 스타일을 유지할지 아니면 새로운 색깔을 선보일지 주목된다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_note_without_exact_quotes_is_rejected() -> None:
    note = GeminiNote(
        source_quote="words that are absent",
        translation_quote="cụm từ không tồn tại",
        category=AmbiguityCategory.CULTURAL_CONTEXT,
        explanation="This note cannot be grounded.",
    )

    flags = build_flags(
        source_text="The ceremony began.",
        primary_text="Buổi lễ bắt đầu.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[note],
        shadow_similarity=0.98,
        back_translation_similarity=None,
    )

    assert flags == []


def test_cultural_note_is_not_presented_as_factual_risk() -> None:
    note = GeminiNote(
        source_quote="눈치",
        translation_quote="social awareness",
        category=AmbiguityCategory.CULTURAL_CONTEXT,
        explanation="The Korean term carries an interpersonal nuance.",
        alternative="reading the room",
    )

    flags = build_flags(
        source_text="그는 눈치가 빠르다.",
        primary_text="He has strong social awareness.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[note],
        shadow_similarity=0.8,
        back_translation_similarity=0.84,
    )

    assert flags[0].kind is FlagKind.CULTURAL_NOTE
    assert flags[0].confidence is None


def test_repeated_date_formatting_does_not_create_a_number_mismatch() -> None:
    flags = build_flags(
        source_text="Ngày 27 tháng 4 (27/04), nhóm đã xuất hiện.",
        primary_text="4월 27일, 그룹이 모습을 드러냈다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_vietnamese_number_words_match_korean_digits() -> None:
    flags = build_flags(
        source_text="Bốn nhạc sĩ hợp tác với ba thành viên trong tám tháng.",
        primary_text="작곡가 4명이 멤버 3명과 8개월 동안 협업했다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


@pytest.mark.parametrize(
    ("source_text", "primary_text"),
    [
        ("Thứ Hai, ngày 27 tháng 4, nhóm đã xuất hiện.", "On Monday, April 27, they appeared."),
        ("Yêu cầu được gửi vào thứ Sáu.", "The request was submitted on Friday."),
    ],
)
def test_vietnamese_weekday_is_not_treated_as_a_number(source_text: str, primary_text: str) -> None:
    flags = build_flags(
        source_text=source_text,
        primary_text=primary_text,
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


@pytest.mark.parametrize(
    ("source_text", "primary_text", "target_language"),
    [
        (
            'Đây là EP thứ hai "Get Up".',
            'This is the second EP "Get Up."',
            Language.ENGLISH,
        ),
        (
            'Đây là EP thứ hai "Get Up".',
            '두 번째 EP "Get Up"이다.',
            Language.KOREAN,
        ),
    ],
)
def test_vietnamese_ordinals_match_translated_ordinals(
    source_text: str,
    primary_text: str,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text=source_text,
        primary_text=primary_text,
        source_language=Language.VIETNAMESE,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_plain_day_is_not_treated_as_number_one() -> None:
    flags = build_flags(
        source_text="평온한 하루 속 팬들을 떠올렸다.",
        primary_text="They thought of their fans during a peaceful day.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_plain_day_matches_explicit_vietnamese_one_day() -> None:
    flags = build_flags(
        source_text="평온한 하루 속 팬들을 떠올렸다.",
        primary_text="Các thành viên nhớ đến người hâm mộ trong một ngày bình yên.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


@pytest.mark.parametrize(
    ("source_text", "primary_text", "source_language", "target_language"),
    [
        (
            "The group returned after a hiatus.",
            "Nhóm trở lại sau thời gian vắng bóng.",
            Language.ENGLISH,
            Language.VIETNAMESE,
        ),
        (
            "Nhóm trở lại sau thời gian gián đoạn.",
            "그룹은 공백기 후 복귀했다.",
            Language.VIETNAMESE,
            Language.KOREAN,
        ),
        (
            "The group returned after a period of inactivity.",
            "Nhóm trở lại sau thời gian gián đoạn.",
            Language.ENGLISH,
            Language.VIETNAMESE,
        ),
        (
            "The group was on hiatus.",
            "Nhóm đã tạm dừng hoạt động.",
            Language.ENGLISH,
            Language.VIETNAMESE,
        ),
    ],
)
def test_hiatus_equivalents_do_not_create_negation_warning(
    source_text: str,
    primary_text: str,
    source_language: Language,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text=source_text,
        primary_text=primary_text,
        source_language=source_language,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_copying_verb_is_not_mistaken_for_negation() -> None:
    flags = build_flags(
        source_text="The publisher claims the song lifts instrumentals from another track.",
        primary_text="Nhà xuất bản cho rằng bài hát lấy phần nhạc cụ từ ca khúc khác.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


@pytest.mark.parametrize(
    ("primary_text", "target_language"),
    [
        (
            "The publisher claims the song misappropriated another work.",
            Language.ENGLISH,
        ),
        ("The publisher says the song was plagiarized.", Language.ENGLISH),
        ("Nhà xuất bản cho rằng bài hát đã đạo nhạc phẩm khác.", Language.VIETNAMESE),
    ],
)
def test_korean_copying_term_matches_translation(
    primary_text: str,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text="출판사는 곡이 다른 작품을 도용했다고 주장했다.",
        primary_text=primary_text,
        source_language=Language.KOREAN,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_lifted_backing_track_matches_vietnamese_equivalent() -> None:
    flags = build_flags(
        source_text="The publisher claims the song lifts music from another track.",
        primary_text="Nhà xuất bản cho rằng bài hát lấy phần nhạc nền từ ca khúc khác.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


@pytest.mark.parametrize(
    ("target_language", "primary_text"),
    [
        (
            Language.ENGLISH,
            "We gathered the members' hearts because they wanted to celebrate together.",
        ),
        (
            Language.VIETNAMESE,
            "Chúng tôi đã tập hợp tấm lòng của các thành viên muốn cùng chúc mừng.",
        ),
    ],
)
def test_literal_korean_gather_hearts_idiom_is_flagged(
    target_language: Language,
    primary_text: str,
) -> None:
    flags = build_flags(
        source_text="멤버들의 마음을 모았다.",
        primary_text=primary_text,
        source_language=Language.KOREAN,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert len(flags) == 1
    assert flags[0].category is AmbiguityCategory.IDIOM
    assert flags[0].kind is FlagKind.CULTURAL_NOTE


def test_model_note_about_source_factual_inconsistency_is_not_a_translation_flag() -> None:
    note = GeminiNote(
        source_quote="약 2년 만에",
        translation_quote="about two years",
        category=AmbiguityCategory.NUMBER,
        explanation=(
            "The source contains a factual contradiction, but the translation "
            "preserves the original phrasing."
        ),
    )
    flags = build_flags(
        source_text="2024년 이후 약 2년 만에 돌아왔다.",
        primary_text="They returned after about two years since 2024.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[note],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert flags == []


def test_korean_number_words_match_vietnamese_number_words() -> None:
    flags = build_flags(
        source_text="이 세 멤버는 그룹에 복귀했다.",
        primary_text="Ba thành viên này đã trở lại nhóm.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_five_members_matches_contextual_vietnamese_number_word() -> None:
    flags = build_flags(
        source_text="뉴진스 다섯 멤버가 복귀했다.",
        primary_text="Năm thành viên NewJeans đã trở lại.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_english_group_words_match_korean_digits() -> None:
    flags = build_flags(
        source_text="The quintet may return as a trio after six months.",
        primary_text="5인조 그룹은 6개월 후 3인조로 복귀할 수 있다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_both_matches_vietnamese_and_korean_number_words() -> None:
    cases = (
        (
            "Both songs use the same rhythm.",
            "Cả hai bài hát dùng cùng một nhịp.",
            Language.VIETNAMESE,
        ),
        ("Both songs use the same rhythm.", "두 곡은 같은 리듬을 쓴다.", Language.KOREAN),
    )

    for source_text, primary_text, target_language in cases:
        flags = build_flags(
            source_text=source_text,
            primary_text=primary_text,
            source_language=Language.ENGLISH,
            target_language=target_language,
            notes=[],
            shadow_similarity=0.95,
            back_translation_similarity=None,
        )

        assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_two_way_matches_english_number_word() -> None:
    flags = build_flags(
        source_text="쌍방향 소통이 이뤄졌다.",
        primary_text="Two-way communication took place.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_digits_attached_to_korean_words_are_compared() -> None:
    flags = build_flags(
        source_text="서울중앙지법 민사합의31부는 2029년 7월31일까지라고 밝혔다.",
        primary_text="The 31st Civil Division said it would last until July 31, 2029.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_clock_minute_formatting_does_not_add_zero() -> None:
    flags = build_flags(
        source_text="재판은 오전 10시에 열린다.",
        primary_text="The hearing begins at 10:00 AM.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_first_trial_terms_match_korean_digit_form() -> None:
    flags = build_flags(
        source_text="The members lost the first trial.",
        primary_text="멤버들은 1심에서 패소했다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_first_hearing_matches_vietnamese_ordinal_form() -> None:
    flags = build_flags(
        source_text="The first hearing begins Thursday.",
        primary_text="Phiên tòa đầu tiên bắt đầu vào thứ Năm.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_first_hearing_matches_vietnamese_ordinal_form() -> None:
    flags = build_flags(
        source_text="첫 변론준비기일이 열린다.",
        primary_text="Phiên chuẩn bị xét xử đầu tiên sẽ diễn ra.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_vietnamese_first_trial_matches_korean_digit_form() -> None:
    flags = build_flags(
        source_text="Nhóm đã thua trong phiên tòa đầu tiên.",
        primary_text="그룹은 1심에서 패소했다.",
        source_language=Language.VIETNAMESE,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_modal_may_is_not_treated_as_a_month() -> None:
    flags = build_flags(
        source_text="May a good opportunity come again.",
        primary_text="좋은 기회가 다시 오기를.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


@pytest.mark.parametrize(
    ("source_text", "primary_text", "target_language"),
    [
        ("Neither member appeared.", "Cả hai thành viên đều không xuất hiện.", Language.VIETNAMESE),
        (
            "Her status remains unresolved.",
            "Tình trạng của cô vẫn chưa được giải quyết.",
            Language.VIETNAMESE,
        ),
        ("They are largely inactive.", "Họ phần lớn không hoạt động.", Language.VIETNAMESE),
        (
            "Nothing can divide us.",
            "우리를 갈라놓을 수 있는 것은 아무것도 없다.",
            Language.KOREAN,
        ),
        (
            "Her status remains unresolved.",
            "그녀의 거취는 여전히 불투명하다.",
            Language.KOREAN,
        ),
        (
            "They have been largely inactive.",
            "이들은 활동을 거의 중단한 상태다.",
            Language.KOREAN,
        ),
        (
            "They cautioned against assuming a return.",
            "복귀를 단정하는 것을 경계했다.",
            Language.KOREAN,
        ),
    ],
)
def test_semantic_negation_equivalents_do_not_create_false_flags(
    source_text: str,
    primary_text: str,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text=source_text,
        primary_text=primary_text,
        source_language=Language.ENGLISH,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_unrelated_matches_korean_equivalent() -> None:
    flags = build_flags(
        source_text="The relatives are unrelated to the contract.",
        primary_text="가족들은 계약과 무관하다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_rejected_matches_korean_negation_equivalent() -> None:
    flags = build_flags(
        source_text="The court rejected the request.",
        primary_text="법원은 요청을 받아들이지 않았다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_first_and_duration_forms_match_across_languages() -> None:
    flags = build_flags(
        source_text="The first group content arrived after one year.",
        primary_text="Nội dung nhóm đầu tiên xuất hiện sau một năm.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_paired_vietnamese_construction_matches_both() -> None:
    flags = build_flags(
        source_text="Nhóm thể hiện cả giọng hát lẫn khả năng sân khấu.",
        primary_text="The group showed both its vocals and stage skills.",
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_compound_won_matches_combined_currency_value() -> None:
    flags = build_flags(
        source_text="손해배상액은 한화 2억 2,700만 원이다.",
        primary_text="Damages total 227 million won.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_sixteenth_note_term_is_not_a_missing_number() -> None:
    flags = build_flags(
        source_text="리듬은 16분음표로 구성됐다.",
        primary_text="Nhịp điệu gồm các nốt móc kép.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_midnight_matches_korean_zero_hour() -> None:
    flags = build_flags(
        source_text="영상은 22일 0시에 공개됐다.",
        primary_text="The video was released at midnight on the 22nd.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_midnight_matches_korean_word_form() -> None:
    flags = build_flags(
        source_text="The video was released at midnight.",
        primary_text="영상은 자정에 공개됐다.",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_korean_one_day_and_both_aspects_match_vietnamese() -> None:
    flags = build_flags(
        source_text="하루 만에 보컬과 무대 양면을 보여줬다.",
        primary_text="Sau một ngày, nhóm thể hiện cả giọng hát lẫn sân khấu.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_english_ordinals_match_vietnamese_number_words() -> None:
    flags = build_flags(
        source_text="The fourth anniversary included the original fifth member.",
        primary_text="Kỷ niệm bốn năm có thành viên thứ 5 ban đầu.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_first_time_phrase_does_not_invent_the_number_one() -> None:
    flags = build_flags(
        source_text="약 2년 만에 멤버들이 모였다.",
        primary_text="The members met for the first time in about two years.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


@pytest.mark.parametrize(
    ("primary_text", "target_language"),
    [
        (
            "The current plan lists at least 24 computers; that does not mean all "
            "24 machines will work on the first day.",
            Language.ENGLISH,
        ),
        (
            "현재 계획에는 최소 24대의 컴퓨터가 포함되지만, 24대 모두가 "
            "첫날부터 작동한다는 뜻은 아니다.",
            Language.KOREAN,
        ),
    ],
)
def test_vietnamese_first_day_matches_translated_ordinal(
    primary_text: str,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text=(
            "Kế hoạch có ít nhất 24 máy tính; điều đó không đồng nghĩa cả 24 máy "
            "đều hoạt động ngay ngày đầu."
        ),
        primary_text=primary_text,
        source_language=Language.VIETNAMESE,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


@pytest.mark.parametrize(
    ("primary_text", "target_language"),
    [
        (
            "This does not promise that all 24 zones will open from the first day.",
            Language.ENGLISH,
        ),
        (
            "Điều đó không cam kết rằng tất cả 24 khu vực sẽ mở từ ngày đầu tiên.",
            Language.VIETNAMESE,
        ),
    ],
)
def test_korean_all_does_not_invent_the_number_two(
    primary_text: str,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text="첫날부터 24개 구역을 모두 개방하겠다고 약속한 것은 아니다.",
        primary_text=primary_text,
        source_language=Language.KOREAN,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)


def test_vietnamese_conditional_otherwise_is_not_a_negation_mismatch() -> None:
    flags = build_flags(
        source_text=(
            "Nếu thử nghiệm đạt yêu cầu, phòng đọc có thể mở vào ngày 12/10; "
            "nếu không, lịch sẽ chuyển sang tháng 11."
        ),
        primary_text=(
            "If the test meets requirements, the reading room may open on October 12; "
            "otherwise, the schedule will shift to November."
        ),
        source_language=Language.VIETNAMESE,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_ranking_abbreviation_is_not_negation() -> None:
    flags = build_flags(
        source_text="The group reached No. 1.",
        primary_text="Nhóm đã đạt vị trí số 1.",
        source_language=Language.ENGLISH,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_vietnamese_atmosphere_is_not_negation() -> None:
    flags = build_flags(
        source_text="분위기가 눈길을 끈다.",
        primary_text="Không khí thu hút sự chú ý.",
        source_language=Language.KOREAN,
        target_language=Language.VIETNAMESE,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


@pytest.mark.parametrize(
    ("source_text", "primary_text", "target_language"),
    [
        ("The band demanded a halt.", "밴드는 중단을 요구했다.", Language.KOREAN),
        (
            "ADOR denied unauthorized use.",
            "ADOR phủ nhận việc sử dụng trái phép.",
            Language.VIETNAMESE,
        ),
        ("Her contract was terminated.", "계약은 해지됐다.", Language.KOREAN),
        ("She was removed from the group.", "Cô bị loại khỏi nhóm.", Language.VIETNAMESE),
        ("The group was on hiatus.", "그룹은 활동을 중단했다.", Language.KOREAN),
        ("Activities were interrupted.", "Hoạt động bị gián đoạn.", Language.VIETNAMESE),
        ("The contract is terminating.", "Hợp đồng đang chấm dứt.", Language.VIETNAMESE),
        ("The song lifts instrumentals.", "곡의 연주를 무단 사용했다.", Language.KOREAN),
    ],
)
def test_semantic_cessation_and_denial_terms_match(
    source_text: str,
    primary_text: str,
    target_language: Language,
) -> None:
    flags = build_flags(
        source_text=source_text,
        primary_text=primary_text,
        source_language=Language.ENGLISH,
        target_language=target_language,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NEGATION for flag in flags)


def test_note_that_says_the_translation_preserves_the_choice_is_suppressed() -> None:
    note = GeminiNote(
        source_quote="약 2년",
        translation_quote="about two years",
        category=AmbiguityCategory.NUMBER,
        explanation="The translation preserves the source's numerical claim.",
    )
    flags = build_flags(
        source_text="약 2년 만에 돌아왔다.",
        primary_text="It returned after about two years.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[note],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert flags == []


def test_note_that_says_the_translation_does_not_preserve_a_choice_remains() -> None:
    note = GeminiNote(
        source_quote="말씀하셨다",
        translation_quote="spoke",
        category=AmbiguityCategory.HONORIFIC,
        explanation="English does not preserve the honorific respect in the Korean verb.",
    )
    flags = build_flags(
        source_text="할머니께서 말씀하셨다.",
        primary_text="Grandmother spoke.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[note],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert [flag.category for flag in flags] == [AmbiguityCategory.HONORIFIC]


def test_preservation_claim_with_an_omission_remains_visible() -> None:
    note = GeminiNote(
        source_quote="퇴출",
        translation_quote="left",
        category=AmbiguityCategory.LEXICAL,
        explanation="The translation conveys departure but omits the forced nature of the exit.",
    )
    flags = build_flags(
        source_text="그는 팀에서 퇴출됐다.",
        primary_text="He left the team.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[note],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert [flag.category for flag in flags] == [AmbiguityCategory.LEXICAL]


def test_three_item_korean_all_list_is_not_assumed_to_mean_two() -> None:
    flags = build_flags(
        source_text="'A', 'B', 'C' 모두 공개됐다.",
        primary_text="All three of A, B, and C were released.",
        source_language=Language.KOREAN,
        target_language=Language.ENGLISH,
        notes=[],
        shadow_similarity=0.95,
        back_translation_similarity=None,
    )

    assert not any(flag.category is AmbiguityCategory.NUMBER for flag in flags)
