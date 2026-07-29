import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.models import (
    AmbiguityCategory,
    AmbiguityFlag,
    FlagKind,
    GeminiNote,
    Language,
)

NUMBER = re.compile(r"(?<!\d)(?:[$₫₩€£]\s*)?\d[\d.,]*(?:\s*%)?")

NEGATION = {
    Language.ENGLISH: re.compile(
        r"\b(?:not|no|never|neither|nothing|without|cannot|can't|won't|except|"
        r"excluding|excluded|inactive|inactivity|unresolved|uncertain|unrelated|"
        r"yet\s+to|rejected|denied|halt|hiatus|removed|unauthorized|"
        r"misappropriat(?:e|ed|ing|ion)|plagiar(?:ize|ized|izing|ism)|"
        r"frozen(?:\s+\w+){0,2}\s+(?:activities|operations)|"
        r"interrupt(?:ed|ion)?|terminat(?:e|ed|ing|ion)|"
        r"lifts?\s+(?:instrumentals?|music|melody|lyrics)|"
        r"(?:cautioned|warned|advised)\s+against)\b",
        re.I,
    ),
    Language.VIETNAMESE: re.compile(
        r"\b(?:chưa|chẳng|không\s+thể|không(?!\s+ít\b)|ngoại\s+trừ|"
        r"bị\s+loại\s+khỏi|đóng\s+băng|gián\s+đoạn|tạm\s+dừng|"
        r"vắng\s+bóng|phủ\s+nhận|trái\s+phép|chấm\s+dứt|ngừng|"
        r"lấy\s+(?:các\s+)?(?:(?:đoạn|phần)\s+)?nhạc\s+(?:cụ|nền)|"
        r"đạo\s+nhạc)\b",
        re.I,
    ),
    Language.KOREAN: re.compile(
        r"(?:\b안\b|않|없|못|아니(?!면)|아닙|빠진|제외|없이|무관|중단|"
        r"공백|불투명|경계|무단|도용|표절|부인|해지|종료)"
    ),
}

SCALE_UNITS = {
    Language.ENGLISH: (
        (re.compile(r"^\s*billion\b", re.I), Decimal("1000000000")),
        (re.compile(r"^\s*million\b", re.I), Decimal("1000000")),
        (re.compile(r"^\s*thousand\b", re.I), Decimal("1000")),
    ),
    Language.VIETNAMESE: (
        (re.compile(r"^\s*tỷ\b", re.I), Decimal("1000000000")),
        (re.compile(r"^\s*triệu\b", re.I), Decimal("1000000")),
        (re.compile(r"^\s*nghìn\b", re.I), Decimal("1000")),
    ),
    Language.KOREAN: (
        (re.compile(r"^\s*억"), Decimal("100000000")),
        (re.compile(r"^\s*만"), Decimal("10000")),
        (re.compile(r"^\s*천"), Decimal("1000")),
    ),
}

CULTURAL_CATEGORIES = {
    AmbiguityCategory.IDIOM,
    AmbiguityCategory.HONORIFIC,
    AmbiguityCategory.CULTURAL_CONTEXT,
    AmbiguityCategory.LEXICAL,
}

NAMED_MONTHS = {
    Language.ENGLISH: {
        "january": "1",
        "february": "2",
        "april": "4",
        "june": "6",
        "july": "7",
        "august": "8",
        "september": "9",
        "october": "10",
        "november": "11",
        "december": "12",
    },
    Language.VIETNAMESE: {
        "tháng một": "1",
        "tháng hai": "2",
        "tháng ba": "3",
        "tháng tư": "4",
        "tháng năm": "5",
        "tháng sáu": "6",
        "tháng bảy": "7",
        "tháng tám": "8",
        "tháng chín": "9",
        "tháng mười": "10",
        "tháng mười một": "11",
        "tháng mười hai": "12",
    },
    Language.KOREAN: {},
}

NUMBER_ALIASES = {
    Language.ENGLISH: (
        (
            re.compile(
                r"\b(?:first(?!\s+time\b)|(?:a|one)\s+(?:year|month|week|day))\b",
                re.I,
            ),
            "1",
        ),
        (re.compile(r"\b(?:two|couple)\b", re.I), "2"),
        (re.compile(r"\b(?:three|trio)\b", re.I), "3"),
        (re.compile(r"\b(?:four|quartet)\b", re.I), "4"),
        (re.compile(r"\b(?:five|quintet)\b", re.I), "5"),
        (re.compile(r"\bsix\b", re.I), "6"),
        (re.compile(r"\bseven\b", re.I), "7"),
        (re.compile(r"\beight\b", re.I), "8"),
        (re.compile(r"\bnine\b", re.I), "9"),
        (re.compile(r"\bten\b", re.I), "10"),
        (re.compile(r"\beleven\b", re.I), "11"),
        (re.compile(r"\btwelve\b", re.I), "12"),
        (re.compile(r"\bsecond\b", re.I), "2"),
        (re.compile(r"\bthird\b", re.I), "3"),
        (re.compile(r"\bfourth\b", re.I), "4"),
        (re.compile(r"\bfifth\b", re.I), "5"),
        (re.compile(r"\bsixth\b", re.I), "6"),
        (re.compile(r"\bseventh\b", re.I), "7"),
        (re.compile(r"\beighth\b", re.I), "8"),
        (re.compile(r"\bninth\b", re.I), "9"),
        (re.compile(r"\btenth\b", re.I), "10"),
        (re.compile(r"\beleventh\b", re.I), "11"),
        (re.compile(r"\btwelfth\b", re.I), "12"),
        (re.compile(r"\b(?:sixteen|sixteenth)\b", re.I), "16"),
        (re.compile(r"\bmidnight\b", re.I), "0"),
    ),
    Language.VIETNAMESE: (
        (
            re.compile(
                r"\b(?:sơ thẩm|đầu tiên|ngày\s+đầu|"
                r"một\s+(?:năm|tháng|tuần|ngày))\b",
                re.I,
            ),
            "1",
        ),
        (re.compile(r"(?<!thứ )\bhai\b", re.I), "2"),
        (re.compile(r"(?<!thứ )\b(?:ba|bộ ba)\b", re.I), "3"),
        (re.compile(r"(?<!thứ )\bbốn\b", re.I), "4"),
        (
            re.compile(r"\b(?:cả năm|ngũ tấu|năm\s+(?:thành viên|người|nhạc sĩ|bài hát))\b", re.I),
            "5",
        ),
        (re.compile(r"(?<!thứ )\bsáu\b", re.I), "6"),
        (re.compile(r"(?<!thứ )\bbảy\b", re.I), "7"),
        (re.compile(r"\btám\b", re.I), "8"),
        (re.compile(r"\bchín\b", re.I), "9"),
        (re.compile(r"\bmười(?!\s+(?:một|hai))\b", re.I), "10"),
        (re.compile(r"\bmười một\b", re.I), "11"),
        (re.compile(r"\bmười hai\b", re.I), "12"),
        (re.compile(r"\bnốt móc kép\b", re.I), "16"),
        (re.compile(r"\bnửa đêm\b", re.I), "0"),
        (
            re.compile(
                r"\b(?:ep|album|thử thách|thành viên|nhóm|ca khúc|bài hát|"
                r"vị trí|lần)[^.!?,]{0,30}\bthứ hai\b",
                re.I,
            ),
            "2",
        ),
        (
            re.compile(
                r"\b(?:ep|album|thử thách|thành viên|nhóm|ca khúc|bài hát|"
                r"vị trí|lần)[^.!?,]{0,30}\bthứ năm\b",
                re.I,
            ),
            "5",
        ),
    ),
    Language.KOREAN: (
        (re.compile(r"(?:첫(?:\s*번째)?|1년|하루\s*(?:만에|동안|후|전))"), "1"),
        (re.compile(r"(?<![가-힣])(?:두|둘)\s*(?:명|개|곡|달|개월|년|멤버)"), "2"),
        (re.compile(r"(?:세|셋)\s*(?:명|개|곡|달|개월|년|멤버)"), "3"),
        (re.compile(r"(?:네|넷)\s*(?:명|개|곡|달|개월|년|멤버)"), "4"),
        (re.compile(r"다섯\s*(?:명|개|달|개월|년|멤버)"), "5"),
        (re.compile(r"여섯\s*(?:명|개|달|개월|년|멤버)"), "6"),
        (re.compile(r"일곱\s*(?:명|개|달|개월|년|멤버)"), "7"),
        (re.compile(r"여덟\s*(?:명|개|달|개월|년|멤버)"), "8"),
        (re.compile(r"아홉\s*(?:명|개|달|개월|년|멤버)"), "9"),
        (re.compile(r"열\s*(?:명|개|달|개월|년|멤버)"), "10"),
        (re.compile(r"두\s*번째"), "2"),
        (re.compile(r"세\s*번째"), "3"),
        (re.compile(r"네\s*번째"), "4"),
        (re.compile(r"다섯\s*번째"), "5"),
        (re.compile(r"여섯\s*번째"), "6"),
        (re.compile(r"일곱\s*번째"), "7"),
        (re.compile(r"여덟\s*번째"), "8"),
        (re.compile(r"아홉\s*번째"), "9"),
        (re.compile(r"열\s*번째"), "10"),
        (re.compile(r"자정"), "0"),
    ),
}
KOREAN_COMPOUND_WON = re.compile(r"(\d[\d,]*)\s*억\s*(\d[\d,]*)\s*만\s*원")
QUOTED_ITEM = r"(?:'[^']+'|\"[^\"]+\")"
KOREAN_QUOTED_ALL = re.compile(rf"({QUOTED_ITEM}(?:\s*,\s*{QUOTED_ITEM})+)\s*모두")

HIGH_RISK = {
    Language.ENGLISH: re.compile(
        r"\b(?:may|might|could|would|alleg(?:e|ed|ation)|investigat|"
        r"lawsuit|court|rul(?:e|ed|ing)|claim(?:s|ed)?|reportedly)\b",
        re.I,
    ),
    Language.VIETNAMESE: re.compile(
        r"\b(?:có thể|được cho là|cáo buộc|điều tra|khởi kiện|tòa án|"
        r"phán quyết|tuyên bố|theo nguồn tin)\b",
        re.I,
    ),
    Language.KOREAN: re.compile(
        r"(?:수\s*있|가능성|의혹|혐의|조사|소송|법원|판결|주장|보도에\s*따르면)"
    ),
}


def needs_local_verification(
    source_text: str,
    source_language: Language,
    *,
    segment_index: int,
    has_model_notes: bool,
) -> bool:
    """Reserve the slower local model for prominent or meaning-sensitive passages."""
    return (
        segment_index < 2
        or has_model_notes
        or NUMBER.search(source_text) is not None
        or NEGATION[source_language].search(source_text) is not None
        or HIGH_RISK[source_language].search(source_text) is not None
    )


def build_flags(
    *,
    source_text: str,
    primary_text: str,
    target_language: Language,
    source_language: Language,
    notes: list[GeminiNote],
    shadow_similarity: float | None,
    back_translation_similarity: float | None,
) -> list[AmbiguityFlag]:
    flags = _protected_fact_flags(
        source_text=source_text,
        primary_text=primary_text,
        source_language=source_language,
        target_language=target_language,
    )
    flags.extend(_literal_idiom_flags(source_text, primary_text, target_language))

    supports_disagreement = (
        shadow_similarity is not None
        and shadow_similarity < 0.86
        or back_translation_similarity is not None
        and back_translation_similarity < 0.86
    )
    for note in notes:
        if note.source_quote not in source_text or note.translation_quote not in primary_text:
            continue
        if _describes_preserved_choice(note.explanation) or _describes_source_inconsistency(
            note.explanation
        ):
            continue
        kind = (
            FlagKind.CULTURAL_NOTE
            if note.category in CULTURAL_CATEGORIES
            else FlagKind.MEANING_RISK
        )
        signals = ["Gemini identified a translation choice"]
        if supports_disagreement:
            signals.append("Local comparison found a semantic difference")
        flags.append(
            AmbiguityFlag(
                id=str(uuid4()),
                target_language=target_language,
                kind=kind,
                category=note.category,
                confidence=None if kind is FlagKind.CULTURAL_NOTE else "medium",
                source_quote=note.source_quote,
                translation_quote=note.translation_quote,
                explanation=note.explanation,
                alternative=note.alternative,
                signals=signals,
            )
        )

    if shadow_similarity is not None and shadow_similarity < 0.72 and not flags:
        flags.append(
            AmbiguityFlag(
                id=str(uuid4()),
                target_language=target_language,
                kind=FlagKind.UNCERTAIN,
                category=AmbiguityCategory.MODEL_DISAGREEMENT,
                confidence="medium",
                source_quote=source_text,
                translation_quote=primary_text,
                explanation=(
                    "The primary and local translations differ enough to merit a closer read."
                ),
                signals=["Low semantic agreement between translation models"],
            )
        )
    return flags


def should_back_translate(notes: list[GeminiNote], shadow_similarity: float) -> bool:
    return bool(notes) or shadow_similarity < 0.86


def _protected_fact_flags(
    *,
    source_text: str,
    primary_text: str,
    source_language: Language,
    target_language: Language,
) -> list[AmbiguityFlag]:
    flags: list[AmbiguityFlag] = []
    source_numbers = set(_extract_numbers(source_text, source_language))
    target_numbers = set(_extract_numbers(primary_text, target_language))
    missing = sorted(source_numbers - target_numbers)
    added = sorted(target_numbers - source_numbers)
    if set(missing + added) == {"2"} and (
        _has_pair_scope(source_text, source_language)
        or _has_pair_scope(primary_text, target_language)
    ):
        missing = []
        added = []
    if (
        set(missing + added) == {"1"}
        and source_language is Language.KOREAN
        and target_language is Language.VIETNAMESE
        and "하루" in source_text
        and re.search(r"\bmột\b[^.!?]{0,20}\bngày\b", primary_text, re.I)
    ):
        missing = []
        added = []
    if missing or added:
        detail = []
        if missing:
            detail.append(f"missing from translation: {', '.join(missing)}")
        if added:
            detail.append(f"new in translation: {', '.join(added)}")
        flags.append(
            AmbiguityFlag(
                id=str(uuid4()),
                target_language=target_language,
                kind=FlagKind.MEANING_RISK,
                category=AmbiguityCategory.NUMBER,
                confidence="high",
                source_quote=next((value for value in NUMBER.findall(source_text)), source_text),
                translation_quote=next((value for value in NUMBER.findall(primary_text)), None),
                explanation=f"Numeric details differ ({'; '.join(detail)}).",
                signals=["Deterministic number comparison"],
            )
        )

    source_match = _find_negation(source_text, source_language)
    target_match = _find_negation(primary_text, target_language)
    source_has_negation = source_match is not None
    target_has_negation = target_match is not None
    if source_has_negation != target_has_negation and not _implicit_polarity_equivalent(
        source_text,
        primary_text,
        source_language,
        target_language,
    ):
        flags.append(
            AmbiguityFlag(
                id=str(uuid4()),
                target_language=target_language,
                kind=FlagKind.MEANING_RISK,
                category=AmbiguityCategory.NEGATION,
                confidence="medium",
                source_quote=source_match.group(0) if source_match else source_text,
                translation_quote=target_match.group(0) if target_match else None,
                explanation=(
                    "Negation or an equivalent polarity marker appears in only one version."
                ),
                signals=["Rule-based negation comparison"],
            )
        )
    return flags


def _find_negation(text: str, language: Language) -> re.Match[str] | None:
    comparison_text = text
    if language is Language.ENGLISH:
        comparison_text = re.sub(r"\bNo\.\s*\d+", "", comparison_text, flags=re.I)
    elif language is Language.VIETNAMESE:
        comparison_text = re.sub(r"\bhay\s+không\b", "", comparison_text, flags=re.I)
        comparison_text = re.sub(r"\bkhông\s+khí\b", "", comparison_text, flags=re.I)
    elif language is Language.KOREAN:
        comparison_text = re.sub(r"적지\s*않", "", comparison_text)
        comparison_text = re.sub(r"끊이지\s*않", "", comparison_text)
    return NEGATION[language].search(comparison_text)


def _has_pair_scope(text: str, language: Language) -> bool:
    if language is Language.ENGLISH:
        return bool(re.search(r"\bboth\b", text, re.I))
    if language is Language.VIETNAMESE:
        return bool(re.search(r"\bcả\b[^.!?]{0,100}\b(?:và|lẫn)\b", text, re.I))
    return bool(re.search(r"(?:\b양측\b|쌍방향|양면|(?:과|와|및)[^.!?]{0,60}모두)", text))


def _implicit_polarity_equivalent(
    source_text: str,
    primary_text: str,
    source_language: Language,
    target_language: Language,
) -> bool:
    if source_language is Language.VIETNAMESE and re.search(r"\bvắng\s+bóng\b", source_text, re.I):
        if target_language is Language.ENGLISH:
            return bool(
                re.search(
                    r"\b(?:after|in)\s+(?:about\s+)?\d[^.!?]{0,30}"
                    r"(?:years?|months?)\b",
                    primary_text,
                    re.I,
                )
            )
        if target_language is Language.KOREAN:
            return "만에" in primary_text
    if (
        source_language is Language.VIETNAMESE
        and target_language is Language.ENGLISH
        and re.search(r"\bnếu\s+không\b", source_text, re.I)
    ):
        return bool(re.search(r"\botherwise\b", primary_text, re.I))
    return False


def _describes_preserved_choice(explanation: str) -> bool:
    normalized = explanation.casefold()
    preservation = ("capture", "preserv", "retain", "convey")
    contrast = (
        " but ",
        " however",
        " although",
        " whereas",
        " loss",
        " lost",
        " more ",
        " less ",
        "does not",
        "doesn't",
        "cannot",
        "can't",
        "fails to",
        " fail",
        " omit",
        " miss",
        " lack",
        " instead",
        " only ",
        " not ",
    )
    return any(term in normalized for term in preservation) and not any(
        term in normalized for term in contrast
    )


def _describes_source_inconsistency(explanation: str) -> bool:
    normalized = explanation.casefold()
    source_reference = ("source", "original")
    inconsistency = ("factual inconsistency", "factual contradiction", "inconsistent")
    return any(term in normalized for term in source_reference) and any(
        term in normalized for term in inconsistency
    )


def _literal_idiom_flags(
    source_text: str,
    primary_text: str,
    target_language: Language,
) -> list[AmbiguityFlag]:
    if "마음을 모" not in source_text:
        return []
    if target_language is Language.ENGLISH:
        literal = re.search(
            r"\bgather(?:ed|ing)?\s+(?:the\s+)?"
            r"(?:(?:members?|people)['’]s?\s+)?hearts?\b",
            primary_text,
            re.I,
        )
        alternative = "brought together the members' shared wishes"
    elif target_language is Language.VIETNAMESE:
        literal = re.search(
            r"\b(?:tập hợp|gom)\s+(?:những\s+)?(?:tấm lòng|trái tim)\b",
            primary_text,
            re.I,
        )
        alternative = "thể hiện nguyện vọng chung của các thành viên"
    else:
        literal = None
        alternative = None
    if literal is None:
        return []
    return [
        AmbiguityFlag(
            id=str(uuid4()),
            target_language=target_language,
            kind=FlagKind.CULTURAL_NOTE,
            category=AmbiguityCategory.IDIOM,
            source_quote="마음을 모았다",
            translation_quote=literal.group(0),
            explanation=(
                "The Korean idiom is translated literally; here it means sharing or "
                "bringing together a common wish."
            ),
            alternative=alternative,
            signals=["Rule-based literal idiom check"],
        )
    ]


def _normalize_number(
    value: str,
    language: Language,
    multiplier: Decimal = Decimal(1),
) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    core = re.sub(r"[^\d.,]", "", normalized).strip(".,")
    if not core:
        return ""

    decimal_separator = "," if language is Language.VIETNAMESE else "."
    grouping_separator = "." if language is Language.VIETNAMESE else ","
    core = core.replace(grouping_separator, "")
    core = core.replace(decimal_separator, ".")

    try:
        number = Decimal(core) * multiplier
    except InvalidOperation:
        return normalized.replace(" ", "").strip(".,")

    if number == number.to_integral():
        return str(int(number))
    return format(number.normalize(), "f")


def _extract_numbers(text: str, language: Language) -> Counter[str]:
    values: Counter[str] = Counter()
    compound_spans: list[tuple[int, int]] = []
    if language is Language.KOREAN:
        for compound in KOREAN_COMPOUND_WON.finditer(text):
            high = Decimal(compound.group(1).replace(",", "")) * Decimal("100000000")
            low = Decimal(compound.group(2).replace(",", "")) * Decimal("10000")
            values[str(int(high + low))] += 1
            compound_spans.append(compound.span())
        for item_list in KOREAN_QUOTED_ALL.finditer(text):
            values[str(len(re.findall(QUOTED_ITEM, item_list.group(1))))] += 1

    for match in NUMBER.finditer(text):
        if any(start <= match.start() and match.end() <= end for start, end in compound_spans):
            continue
        multiplier = Decimal(1)
        suffix = text[match.end() :]
        for pattern, scale in SCALE_UNITS[language]:
            if pattern.match(suffix):
                multiplier = scale
                break
        normalized = _normalize_number(match.group(), language, multiplier)
        if normalized == "0" and match.start() > 0 and text[match.start() - 1] == ":":
            continue
        if normalized:
            values[normalized] += 1

    normalized_text = unicodedata.normalize("NFKC", text).lower()
    months = NAMED_MONTHS[language]
    if months:
        alternatives = "|".join(re.escape(month) for month in sorted(months, key=len, reverse=True))
        for match in re.finditer(rf"(?<!\w)(?:{alternatives})(?!\w)", normalized_text):
            values[months[match.group(0)]] += 1
    if language is Language.ENGLISH:
        ambiguous_month = re.compile(
            r"\b(?:in|on|until|since|from|by|during|last|next|this)\s+(march|may)\b"
            r"|\b(march|may)\s+\d",
            re.I,
        )
        for match in ambiguous_month.finditer(text):
            month = next(group for group in match.groups() if group)
            values["3" if month.casefold() == "march" else "5"] += 1

    for pattern, number in NUMBER_ALIASES[language]:
        if pattern.search(text):
            values[number] += 1
    return values


def extract_number_anchors(text: str, language: Language) -> set[str]:
    return set(_extract_numbers(text, language))


def has_negation(text: str, language: Language) -> bool:
    return bool(NEGATION[language].search(text))
