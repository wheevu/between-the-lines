"""Language detection, normalization, and offset-preserving EN/VI/KO segmentation."""

from __future__ import annotations

import re
import unicodedata

from btl.types import Language, LanguageOrAuto, Segment

VIETNAMESE_MARKS = frozenset(
    "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
)
HANGUL = re.compile(r"[\uac00-\ud7a3]")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])(?:[\"'”’)\]]*)\s+")
SPACE = re.compile(r"[^\S\n]+")
NUMBER_ABBREVIATION = re.compile(r"\bNo\.(?=\s*\d)", re.I)
DOTTED_ABBREVIATION = re.compile(
    r"\b(?:U\.S\.|U\.K\.|E\.U\.)(?=\s+(?:[a-z]|District\b|Court\b|"
    r"government\b|company\b|firm\b|officials?\b|maker\b|market\b|based\b))"
)
PROTECTED_PERIOD = "\u2024"
KOREAN_COPYRIGHT_FOOTER = re.compile(
    r"^(?:(?:※\s*)?이 콘텐츠는 저작권법|무단\s*전재|저작권자).*(?:금합니다|금지)[.!]?\s*$"
)


def detect_language(text: str) -> Language:
    """Detect English, Vietnamese, or Korean from script and diacritic signals."""
    sample = unicodedata.normalize("NFC", text[:2_000]).lower()
    stripped_len = len(sample.strip())
    min_hits = 1 if stripped_len <= 80 else 3
    hangul_count = len(HANGUL.findall(sample))
    vi_count = sum(character in VIETNAMESE_MARKS for character in sample)
    if hangul_count >= min_hits and hangul_count >= vi_count:
        return Language.KOREAN
    if vi_count >= min_hits:
        return Language.VIETNAMESE
    return Language.ENGLISH


def resolve_language(text: str, hint: LanguageOrAuto = "auto") -> Language:
    """Return an explicit Language or auto-detect from text."""
    if hint == "auto":
        return detect_language(text)
    return Language(hint)


def normalize_article(text: str) -> str:
    """Normalize Unicode, strip invisible format chars, deduplicate consecutive lines."""
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Cf"
    )
    paragraphs: list[str] = []
    for raw_paragraph in normalized.split("\n"):
        paragraph = SPACE.sub(" ", raw_paragraph).strip()
        if not paragraph or paragraph.casefold() == "summarize":
            continue
        if len(paragraph) < 250 and KOREAN_COPYRIGHT_FOOTER.match(paragraph):
            continue
        if paragraphs and paragraphs[-1] == paragraph:
            continue
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def segment_article(text: str, language: Language | None = None) -> list[Segment]:
    """Segment normalized text into sentences while tracking exact character offsets."""
    del language  # Boundary punctuation is shared across EN/VI/KO news and policy text.
    normalized = normalize_article(text)
    if not normalized:
        return []

    segments: list[Segment] = []
    cursor = 0
    for paragraph_index, paragraph in enumerate(normalized.split("\n\n")):
        para_start = normalized.find(paragraph, cursor)
        if para_start < 0:
            para_start = cursor
        cursor = para_start + len(paragraph)

        protected = NUMBER_ABBREVIATION.sub(
            lambda match: match.group().replace(".", PROTECTED_PERIOD),
            paragraph,
        )
        protected = DOTTED_ABBREVIATION.sub(
            lambda match: match.group().replace(".", PROTECTED_PERIOD),
            protected,
        )
        parts = [
            part.replace(PROTECTED_PERIOD, ".").strip()
            for part in SENTENCE_BOUNDARY.split(protected)
            if part.strip()
        ]
        sent_cursor = 0
        for sentence_index, sentence in enumerate(parts):
            local_start = paragraph.find(sentence, sent_cursor)
            if local_start < 0:
                local_start = sent_cursor
            start_offset = para_start + local_start
            end_offset = start_offset + len(sentence)
            sent_cursor = local_start + len(sentence)
            segments.append(
                Segment(
                    id=f"p{paragraph_index + 1}s{sentence_index + 1}",
                    paragraph_index=paragraph_index,
                    sentence_index=sentence_index,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text=sentence,
                )
            )
    return segments
