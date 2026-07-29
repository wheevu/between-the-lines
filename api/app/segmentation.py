import re
import unicodedata
from dataclasses import dataclass

from app.models import Language

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


@dataclass(frozen=True)
class Segment:
    id: str
    paragraph_index: int
    sentence_index: int
    text: str


def normalize_article(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Cf"
    )
    paragraphs = []
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


def segment_article(text: str, language: Language) -> list[Segment]:
    del language  # Boundary punctuation is shared by all three supported news formats.
    normalized = normalize_article(text)
    segments: list[Segment] = []
    for paragraph_index, paragraph in enumerate(normalized.split("\n\n")):
        protected = NUMBER_ABBREVIATION.sub(
            lambda match: match.group().replace(".", PROTECTED_PERIOD),
            paragraph,
        )
        protected = DOTTED_ABBREVIATION.sub(
            lambda match: match.group().replace(".", PROTECTED_PERIOD),
            protected,
        )
        sentences = [
            part.replace(PROTECTED_PERIOD, ".").strip()
            for part in SENTENCE_BOUNDARY.split(protected)
            if part.strip()
        ]
        for sentence_index, sentence in enumerate(sentences):
            segments.append(
                Segment(
                    id=f"p{paragraph_index + 1}s{sentence_index + 1}",
                    paragraph_index=paragraph_index,
                    sentence_index=sentence_index,
                    text=sentence,
                )
            )
    return segments
