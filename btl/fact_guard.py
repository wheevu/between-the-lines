"""Deterministic EN/VI/KO translation verification and fact-drift checks."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from btl.language import resolve_language
from btl.types import (
    ClaimModality,
    DriftCategory,
    DriftFlag,
    Language,
    LegalState,
    PairAuditResult,
    TranslationAuditResult,
    TranslationPairInput,
)

NUMBER = re.compile(r"(?<!\d)(?:[$₫₩€£]\s*)?\d[\d.,]*(?:\s*%)?")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|\n+")

DATE_PATTERN = re.compile(
    r"(?:\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b|"
    r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|"
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b|"
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b|"
    r"\bngày\s+\d{1,2}\s+tháng\s+\d{1,2}(?:\s+năm\s+\d{4})?\b|"
    r"\btháng\s+\d{1,2}(?:\s+năm\s+\d{4})?\b|"
    r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일|\d{1,2}월\s*\d{1,2}일|\b(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)

NEGATION = {
    Language.ENGLISH: re.compile(
        r"\b(?:not|no|never|neither|nor|nothing|without|cannot|can't|won't|didn't|doesn't|"
        r"don't|except|excluding|excluded|inactive|inactivity|unresolved|uncertain|unrelated|"
        r"yet\s+to|rejected|denied|halt|halted|hiatus|removed|unauthorized|prohibited|"
        r"banned|forbidden|barred|suspended|interrupt(?:ed|ion)?|terminat(?:e|ed|ing|ion))\b",
        re.I,
    ),
    Language.VIETNAMESE: re.compile(
        r"\b(?:chưa|chẳng|không\s+thể|không(?!\s+ít\b)|ngoại\s+trừ|bị\s+loại\s+khỏi|"
        r"đóng\s+băng|gián\s+đoạn|tạm\s+dừng|vắng\s+bóng|phủ\s+nhận|trái\s+phép|"
        r"chấm\s+dứt|ngừng|cấm|bị\s+cấm|không\s+được)\b",
        re.I,
    ),
    Language.KOREAN: re.compile(
        r"(?:\b안\b|않|없|못|아니(?!면)|아닙|빠진|제외|없이|무관|중단|"
        r"공백|불투명|무단|부인|해지|종료|금지|불허|불가)"
    ),
}

SCALE_UNITS = {
    Language.ENGLISH: (
        (re.compile(r"^\s*trillion\b", re.I), Decimal("1000000000000")),
        (re.compile(r"^\s*billion\b", re.I), Decimal("1000000000")),
        (re.compile(r"^\s*million\b", re.I), Decimal("1000000")),
        (re.compile(r"^\s*thousand\b", re.I), Decimal("1000")),
    ),
    Language.VIETNAMESE: (
        (re.compile(r"^\s*(?:nghìn|ngàn)\s+tỷ\b", re.I), Decimal("1000000000000")),
        (re.compile(r"^\s*tỷ\b", re.I), Decimal("1000000000")),
        (re.compile(r"^\s*triệu\b", re.I), Decimal("1000000")),
        (re.compile(r"^\s*(?:nghìn|ngàn)\b", re.I), Decimal("1000")),
    ),
    Language.KOREAN: (
        (re.compile(r"^\s*조"), Decimal("1000000000000")),
        (re.compile(r"^\s*억"), Decimal("100000000")),
        (re.compile(r"^\s*만"), Decimal("10000")),
        (re.compile(r"^\s*천"), Decimal("1000")),
    ),
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
        (re.compile(r"\b(?:first(?!\s+time\b)|(?:a|one)\s+(?:year|month|week|day))\b", re.I), "1"),
        (re.compile(r"\b(?:two|couple|second)\b", re.I), "2"),
        (re.compile(r"\b(?:three|trio|third)\b", re.I), "3"),
        (re.compile(r"\b(?:four|quartet|fourth)\b", re.I), "4"),
        (re.compile(r"\b(?:five|quintet|fifth)\b", re.I), "5"),
        (re.compile(r"\b(?:six|sixth)\b", re.I), "6"),
        (re.compile(r"\b(?:seven|seventh)\b", re.I), "7"),
        (re.compile(r"\b(?:eight|eighth)\b", re.I), "8"),
        (re.compile(r"\b(?:nine|ninth)\b", re.I), "9"),
        (re.compile(r"\b(?:ten|tenth)\b", re.I), "10"),
        (re.compile(r"\b(?:eleven|eleventh)\b", re.I), "11"),
        (re.compile(r"\b(?:twelve|twelfth)\b", re.I), "12"),
        (re.compile(r"\bmidnight\b", re.I), "0"),
    ),
    Language.VIETNAMESE: (
        (
            re.compile(r"\b(?:sơ thẩm|đầu tiên|ngày\s+đầu|một\s+(?:năm|tháng|tuần|ngày))\b", re.I),
            "1",
        ),
        (re.compile(r"(?<!thứ )\bhai\b", re.I), "2"),
        (re.compile(r"(?<!thứ )\b(?:ba|bộ ba)\b", re.I), "3"),
        (re.compile(r"(?<!thứ )\bbốn\b", re.I), "4"),
        (re.compile(r"(?<!thứ )\b(?:cả năm|ngũ tấu|năm\s+(?:thành viên|người|năm))\b", re.I), "5"),
        (re.compile(r"(?<!thứ )\bsáu\b", re.I), "6"),
        (re.compile(r"(?<!thứ )\bbảy\b", re.I), "7"),
        (re.compile(r"\btám\b", re.I), "8"),
        (re.compile(r"\bchín\b", re.I), "9"),
        (re.compile(r"\bmười(?!\s+(?:một|hai))\b", re.I), "10"),
        (re.compile(r"\bmười một\b", re.I), "11"),
        (re.compile(r"\bmười hai\b", re.I), "12"),
        (re.compile(r"\bnửa đêm\b", re.I), "0"),
        (
            re.compile(
                r"\b(?:lần|vị trí|giai đoạn|phiên bản|chương|điều|khoản|bước)"
                r"[^.!?,]{0,30}\bthứ hai\b",
                re.I,
            ),
            "2",
        ),
        (
            re.compile(
                r"\b(?:lần|vị trí|giai đoạn|phiên bản|chương|điều|khoản|bước)"
                r"[^.!?,]{0,30}\bthứ năm\b",
                re.I,
            ),
            "5",
        ),
    ),
    Language.KOREAN: (
        (re.compile(r"(?:첫(?:\s*번째)?|1년|하루\s*(?:만에|동안|후|전))"), "1"),
        (re.compile(r"(?<![가-힣])(?:두|둘)\s*(?:명|개|곡|달|개월|년|일|주|건|차례|번째)"), "2"),
        (re.compile(r"(?:세|셋)\s*(?:명|개|곡|달|개월|년|일|주|건|차례|번째)"), "3"),
        (re.compile(r"(?:네|넷)\s*(?:명|개|곡|달|개월|년|일|주|건|차례|번째)"), "4"),
        (re.compile(r"다섯\s*(?:명|개|달|개월|년|일|주|건|차례|번째)"), "5"),
        (re.compile(r"여섯\s*(?:명|개|달|개월|년|일|주|건|차례|번째)"), "6"),
        (re.compile(r"일곱\s*(?:명|개|달|개월|년|일|주|건|차례|번째)"), "7"),
        (re.compile(r"여덟\s*(?:명|개|달|개월|년|일|주|건|차례|번째)"), "8"),
        (re.compile(r"아홉\s*(?:명|개|달|개월|년|일|주|건|차례|번째)"), "9"),
        (re.compile(r"열\s*(?:명|개|달|개월|년|일|주|건|차례|번째)"), "10"),
        (re.compile(r"자정"), "0"),
    ),
}

KOREAN_COMPOUND_UNIT = re.compile(r"(\d[\d,]*)\s*억\s*(\d[\d,]*)\s*만(?:\s*(?:원|명|개|달러))?")
QUOTED_ITEM = r"(?:'[^']+'|\"[^\"]+\")"
KOREAN_QUOTED_ALL = re.compile(rf"({QUOTED_ITEM}(?:\s*,\s*{QUOTED_ITEM})+)\s*모두")

FUTURE_PLAN = {
    Language.ENGLISH: re.compile(
        r"\b(?:plan(?:s|ned)?\s+to|expected\s+to|scheduled\s+to|"
        r"predict(?:s|ed)?\s+to|forecast(?:s|ed)?\s+to|will|slated\s+to)\b",
        re.I,
    ),
    Language.VIETNAMESE: re.compile(
        r"\b(?:lên\s+kế\s+hoạch|có\s+kế\s+hoạch|dự\s+kiến|dự\s+báo|sẽ)\b", re.I
    ),
    Language.KOREAN: re.compile(r"(?:계획|예정|예측|전망|것이다|방침)"),
}

UNCERTAINTY = {
    Language.ENGLISH: re.compile(
        r"\b(?:may|might|could|appears?|seems?|suggests?|estimat(?:e|ed)|"
        r"uncertain|likely|unlikely|possibly|probably|reportedly|allegedly)\b",
        re.I,
    ),
    Language.VIETNAMESE: re.compile(
        r"\b(?:có thể|dường như|ước tính|khả năng|chưa chắc|có lẽ|được cho là|nghi)\b",
        re.I,
    ),
    Language.KOREAN: re.compile(
        r"(?:가능성|추정|불확실|것으로\s*보|듯하|지도\s*모르|보도에\s*따르면|의혹)"
    ),
}

DENIAL = {
    Language.ENGLISH: re.compile(
        r"\b(?:den(?:y|ies|ied)|reject(?:s|ed)?|refut(?:e|es|ed))\b", re.I
    ),
    Language.VIETNAMESE: re.compile(r"\b(?:phủ nhận|bác bỏ)\b", re.I),
    Language.KOREAN: re.compile(r"(?:부인|반박|일축)"),
}

LEGAL_STATE = {
    Language.ENGLISH: [
        (
            LegalState.FINDING,
            re.compile(r"\b(?:finding|found liable|convict(?:ed|ion)|guilty)\b", re.I),
        ),
        (
            LegalState.RULING,
            re.compile(r"\b(?:ruling|ruled|judgment|injunction|verdict|sentenced)\b", re.I),
        ),
        (
            LegalState.FILING,
            re.compile(
                r"\b(?:filed|filing|complaint|lawsuit|petition|indict(?:ed|ment))\b", re.I
            ),
        ),
        (
            LegalState.INVESTIGATION,
            re.compile(r"\b(?:investigat(?:e|es|ed|ion)|probe|inquiry)\b", re.I),
        ),
        (
            LegalState.ALLEGATION,
            re.compile(
                r"\b(?:alleg(?:e|es|ed|edly|ation)|accus(?:e|ed|ation)|suspect(?:ed)?)\b",
                re.I,
            ),
        ),
    ],
    Language.VIETNAMESE: [
        (LegalState.FINDING, re.compile(r"\b(?:kết luận|kết tội|có tội)\b", re.I)),
        (
            LegalState.RULING,
            re.compile(r"\b(?:phán quyết|tuyên án|bản án|lệnh cấm)\b", re.I),
        ),
        (
            LegalState.FILING,
            re.compile(r"\b(?:khởi kiện|đơn kiện|nộp đơn|khởi tố|truy tố)\b", re.I),
        ),
        (
            LegalState.INVESTIGATION,
            re.compile(r"\b(?:điều tra|thanh tra|xác minh)\b", re.I),
        ),
        (
            LegalState.ALLEGATION,
            re.compile(r"\b(?:cáo buộc|bị tố|tố cáo|nghi vấn|nghi ngờ)\b", re.I),
        ),
    ],
    Language.KOREAN: [
        (LegalState.FINDING, re.compile(r"(?:유죄|확정|결론|인정됐다)")),
        (LegalState.RULING, re.compile(r"(?:판결|선고|가처분|법원.{0,8}결정)")),
        (LegalState.FILING, re.compile(r"(?:소송|고소|고발|제소|신청서|기소)")),
        (LegalState.INVESTIGATION, re.compile(r"(?:수사|조사|내사)")),
        (LegalState.ALLEGATION, re.compile(r"(?:의혹|혐의|주장|제기)")),
    ],
}

ATTRIBUTION_MARKERS = {
    Language.ENGLISH: re.compile(
        r"\b(?:according\s+to|reportedly|allegedly|cited|citing|stated|claimed|"
        r"said|announced|reported\s+by|per\s+(?:officials|police|the\s+ministry))\b",
        re.I,
    ),
    Language.VIETNAMESE: re.compile(
        r"(?:\btheo\s+(?:nguồn|báo|cơ quan|bộ|cảnh sát|tòa|hãng|ông|bà|tổ chức|"
        r"ủy ban|số liệu|thông báo)\b|\btheo\s+nguồn\s+tin\b|\bđược\s+cho\s+là\b|"
        r"\bcho\s+biết\b|\btuyên\s+bố\b|\bcáo\s+buộc\b|\bnêu\s+rõ\b|"
        r"\bdẫn\s+lời\b|\bdẫn\s+nguồn\b)",
        re.I,
    ),
    Language.KOREAN: re.compile(
        r"(?:에\s*따르면|보도에\s*따르면|관계자는|당국은|측은|밝혔다|주장했다|"
        r"전했다|인용|발표했다|설명했다|보도했다)"
    ),
}
VIETNAMESE_NAMED_THEO = re.compile(r"\b[Tt]heo\s+[A-ZĐÀ-Ỹ][\w.-]{1,}")

LEGAL_RANK = {
    LegalState.ALLEGATION: 1,
    LegalState.INVESTIGATION: 2,
    LegalState.FILING: 3,
    LegalState.RULING: 4,
    LegalState.FINDING: 5,
}


def extract_number_anchors(text: str, language: Language) -> set[str]:
    return set(_extract_numbers(text, language))


def extract_ordered_numbers(text: str, language: Language) -> list[str]:
    return list(dict.fromkeys(_extract_numbers(text, language).keys()))


def has_negation(text: str, language: Language) -> bool:
    return _find_negation(text, language) is not None


def has_uncertainty(text: str, language: Language) -> bool:
    return bool(UNCERTAINTY[language].search(text))


def has_future_plan(text: str, language: Language) -> bool:
    return bool(FUTURE_PLAN[language].search(text))


def has_attribution(text: str, language: Language) -> bool:
    return bool(ATTRIBUTION_MARKERS[language].search(text)) or (
        language is Language.VIETNAMESE and bool(VIETNAMESE_NAMED_THEO.search(text))
    )


def detect_modality(text: str, language: Language) -> ClaimModality:
    if DENIAL[language].search(text):
        return ClaimModality.DENIED
    if FUTURE_PLAN[language].search(text):
        return ClaimModality.FUTURE
    if UNCERTAINTY[language].search(text):
        return ClaimModality.UNCERTAIN
    return ClaimModality.ASSERTED


def detect_legal_state(text: str, language: Language) -> LegalState | None:
    for state, pattern in LEGAL_STATE[language]:
        if pattern.search(text):
            return state
    return None


def anchor_quote(quote: str, text: str) -> str | None:
    """Resolve a literal or punctuation-normalized verbatim substring inside text."""
    if not quote or not text:
        return None
    if quote in text:
        return quote
    normalized_quote = _normalized_chars(quote)
    if not normalized_quote:
        return None
    candidates = [part.strip() for part in SENTENCE_BOUNDARY.split(text) if part.strip()]
    best_candidate: str | None = None
    best_score = 0.0
    for candidate in candidates:
        normalized_candidate = _normalized_chars(candidate)
        if not normalized_candidate:
            continue
        score = SequenceMatcher(None, normalized_quote, normalized_candidate).ratio()
        if score > best_score:
            best_candidate = candidate
            best_score = score
    return best_candidate if best_score >= 0.9 else None


def check_translation_pair(pair: TranslationPairInput, *, index: int = 1) -> PairAuditResult:
    """Audit one source-to-translation pair for numbers, negation, modality, legal state, quotes."""
    src_lang = resolve_language(pair.source_text, pair.source_language)
    tgt_lang = resolve_language(pair.translation_text, pair.target_language)
    flags: list[DriftFlag] = []

    src_numbers = extract_number_anchors(pair.source_text, src_lang)
    tgt_numbers = extract_number_anchors(pair.translation_text, tgt_lang)
    missing = sorted(src_numbers - tgt_numbers)
    added = sorted(tgt_numbers - src_numbers)

    if set(missing + added) == {"2"} and (
        _has_pair_scope(pair.source_text, src_lang)
        or _has_pair_scope(pair.translation_text, tgt_lang)
    ):
        missing, added = [], []
    if (
        set(missing + added) == {"1"}
        and src_lang is Language.KOREAN
        and tgt_lang is Language.VIETNAMESE
        and "하루" in pair.source_text
        and re.search(r"\bmột\b[^.!?]{0,20}\bngày\b", pair.translation_text, re.I)
    ):
        missing, added = [], []

    if missing or added:
        detail_parts: list[str] = []
        if missing:
            detail_parts.append(f"missing from translation: {', '.join(missing)}")
        if added:
            detail_parts.append(f"added in translation: {', '.join(added)}")
        flags.append(
            DriftFlag(
                category=DriftCategory.NUMBER,
                confidence="high",
                source_quote=_first_match(NUMBER, pair.source_text) or pair.source_text[:120],
                translation_quote=_first_match(NUMBER, pair.translation_text),
                explanation=f"Numeric or scale values differ ({'; '.join(detail_parts)}).",
                details={"missing": missing, "added": added},
            )
        )

    src_neg = _find_negation(pair.source_text, src_lang)
    tgt_neg = _find_negation(pair.translation_text, tgt_lang)
    if (src_neg is not None) != (tgt_neg is not None) and not _implicit_polarity_equivalent(
        pair.source_text, pair.translation_text, src_lang, tgt_lang
    ):
        flags.append(
            DriftFlag(
                category=DriftCategory.NEGATION,
                confidence="medium",
                source_quote=src_neg.group(0) if src_neg else pair.source_text[:120],
                translation_quote=tgt_neg.group(0) if tgt_neg else None,
                explanation=(
                    "Negation or an equivalent polarity marker appears in only one version."
                ),
            )
        )

    src_modality = detect_modality(pair.source_text, src_lang)
    tgt_modality = detect_modality(pair.translation_text, tgt_lang)
    if src_modality is not tgt_modality and (
        src_modality in {ClaimModality.UNCERTAIN, ClaimModality.FUTURE, ClaimModality.DENIED}
        and tgt_modality is ClaimModality.ASSERTED
        or tgt_modality in {ClaimModality.UNCERTAIN, ClaimModality.FUTURE, ClaimModality.DENIED}
        and src_modality is ClaimModality.ASSERTED
    ):
        flags.append(
            DriftFlag(
                category=DriftCategory.MODALITY_SHIFT,
                confidence="medium",
                source_quote=pair.source_text[:160],
                translation_quote=pair.translation_text[:160],
                explanation=(
                    f"Modality shifted from {src_modality.value} to {tgt_modality.value}."
                ),
                details={"source": src_modality.value, "translation": tgt_modality.value},
            )
        )

    src_legal = detect_legal_state(pair.source_text, src_lang)
    tgt_legal = detect_legal_state(pair.translation_text, tgt_lang)
    if src_legal is not None and tgt_legal is not None and src_legal is not tgt_legal:
        direction = (
            "elevated" if LEGAL_RANK[tgt_legal] > LEGAL_RANK[src_legal] else "downgraded"
        )
        flags.append(
            DriftFlag(
                category=DriftCategory.LEGAL_STATE_SHIFT,
                confidence="high",
                source_quote=pair.source_text[:160],
                translation_quote=pair.translation_text[:160],
                explanation=(
                    f"Legal stage {direction} from {src_legal.value} to {tgt_legal.value}."
                ),
                details={"source": src_legal.value, "translation": tgt_legal.value},
            )
        )

    if has_attribution(pair.source_text, src_lang) and not has_attribution(
        pair.translation_text, tgt_lang
    ):
        flags.append(
            DriftFlag(
                category=DriftCategory.ATTRIBUTION_LOSS,
                confidence="medium",
                source_quote=pair.source_text[:160],
                translation_quote=pair.translation_text[:160],
                explanation="Explicit attribution in the source text was dropped in translation.",
            )
        )

    if pair.source_quote and not anchor_quote(pair.source_quote, pair.source_text):
        flags.append(
            DriftFlag(
                category=DriftCategory.UNANCHORED_QUOTE,
                confidence="high",
                source_quote=pair.source_quote,
                explanation="Supplied source_quote did not resolve in source_text.",
            )
        )
    if pair.translation_quote and not anchor_quote(pair.translation_quote, pair.translation_text):
        flags.append(
            DriftFlag(
                category=DriftCategory.UNANCHORED_QUOTE,
                confidence="high",
                translation_quote=pair.translation_quote,
                explanation="Supplied translation_quote did not resolve in translation_text.",
            )
        )

    return PairAuditResult(
        pair_id=pair.pair_id or f"pair-{index}",
        source_language=src_lang,
        target_language=tgt_lang,
        status="drift_detected" if flags else "clean",
        flags=flags,
        source_numbers=sorted(src_numbers),
        translation_numbers=sorted(tgt_numbers),
        source_modality=src_modality,
        translation_modality=tgt_modality,
        source_legal_state=src_legal,
        translation_legal_state=tgt_legal,
    )


def audit_translations(pairs: list[TranslationPairInput]) -> TranslationAuditResult:
    """Audit a batch of translation pairs and summarize detected meaning drift."""
    audited = [check_translation_pair(pair, index=idx + 1) for idx, pair in enumerate(pairs)]
    flagged = sum(1 for item in audited if item.status == "drift_detected")
    return TranslationAuditResult(
        status="drift_detected" if flagged > 0 else "clean",
        pair_count=len(audited),
        flagged_count=flagged,
        pairs=audited,
    )


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    found = pattern.search(text)
    return found.group(0) if found else None


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
    translation_text: str,
    source_language: Language,
    target_language: Language,
) -> bool:
    if source_language is Language.VIETNAMESE and re.search(r"\bvắng\s+bóng\b", source_text, re.I):
        if target_language is Language.ENGLISH:
            return bool(
                re.search(
                    r"\b(?:after|in)\s+(?:about\s+)?\d[^.!?]{0,30}(?:years?|months?)\b",
                    translation_text,
                    re.I,
                )
            )
        if target_language is Language.KOREAN:
            return "만에" in translation_text
    if (
        source_language is Language.VIETNAMESE
        and target_language is Language.ENGLISH
        and re.search(r"\bnếu\s+không\b", source_text, re.I)
    ):
        return bool(re.search(r"\botherwise\b", translation_text, re.I))
    return False


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
        for compound in KOREAN_COMPOUND_UNIT.finditer(text):
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


def _normalized_chars(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())
