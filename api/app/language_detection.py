import re

from app.models import Language

VIETNAMESE_MARKS = frozenset("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
HANGUL = re.compile(r"[\uac00-\ud7a3]")


def detect_language(text: str) -> Language:
    sample = text[:2_000].lower()
    if len(HANGUL.findall(sample)) >= 3:
        return Language.KOREAN
    if sum(character in VIETNAMESE_MARKS for character in sample) >= 3:
        return Language.VIETNAMESE
    return Language.ENGLISH
