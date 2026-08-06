"""Regression tests for app.language_detection.detect_language.

Contract derived from the implementation (api/app/language_detection.py), its
call sites (api/app/fact_checker.py and api/app/claim_trace_benchmark.py) and
the ``Language`` enum (api/app/models.py: en/vi/ko).

``detect_language(text)`` inspects ``text[:2000].lower()`` and returns:

- ``Language.KOREAN`` if the sample contains at least 3 Hangul syllable
  characters in the range U+AC00..U+D7A3;
- ``Language.VIETNAMESE`` if the sample contains at least 3 characters from the
  Vietnamese mark set (checked only when the Korean test did not match);
- ``Language.ENGLISH`` otherwise.

Empty and whitespace-only input falls through to ``ENGLISH``. Korean is decided
before Vietnamese, so text with at least 3 Hangul and at least 3 marks is
``KOREAN``. The mark set deliberately overlaps Latin diacritics from other
languages: for example ``"Université de Montréal and Fernández"`` contains 3
marks (é, é, á) and therefore classifies as ``VIETNAMESE`` even though the text
is not Vietnamese. This is a documented heuristic, not a defect to fix.

These tests pin the current intended behavior. They are pure, deterministic and
need no network access or external services.
"""

from app.language_detection import detect_language
from app.models import Language


def test_korean_detection() -> None:
    assert detect_language("이 보고서는 한국어로 작성됐다.") is Language.KOREAN
    assert detect_language("한국어") is Language.KOREAN


def test_korean_negative_falls_through() -> None:
    assert detect_language("한글") is Language.ENGLISH
    assert detect_language("this is not korean text") is Language.ENGLISH


def test_korean_threshold_boundary() -> None:
    assert detect_language("한글") is Language.ENGLISH
    assert detect_language("한국어") is Language.KOREAN


def test_vietnamese_detection() -> None:
    assert detect_language("Báo cáo này có tiếng Việt.") is Language.VIETNAMESE


def test_vietnamese_negative_falls_through() -> None:
    assert detect_language("Người") is Language.ENGLISH
    assert detect_language("plain latin text") is Language.ENGLISH


def test_vietnamese_threshold_boundary() -> None:
    assert detect_language("báo cáo") is Language.ENGLISH
    assert detect_language("báo cáo à") is Language.VIETNAMESE


def test_english_fallback() -> None:
    assert detect_language("The report contains English text.") is Language.ENGLISH
    assert detect_language("The report quoted Université de Montréal.") is Language.ENGLISH
    assert detect_language("Argentina midfielder Enzo Fernández was booked.") is Language.ENGLISH


def test_empty_and_whitespace() -> None:
    assert detect_language("") is Language.ENGLISH
    assert detect_language("   \n\t ") is Language.ENGLISH


def test_2000_character_limit() -> None:
    assert detect_language("a" * 2000 + "한국어") is Language.ENGLISH
    assert detect_language("a" * 1997 + "한국어") is Language.KOREAN


def test_korean_over_vietnamese_priority() -> None:
    assert detect_language("한국어 báo cáo à") is Language.KOREAN


def test_mixed_language_heuristic_false_positive() -> None:
    assert detect_language("Université de Montréal and Fernández") is Language.VIETNAMESE
    assert detect_language("Université de Montréal.") is Language.ENGLISH
