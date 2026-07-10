import re
import unicodedata


class InvalidSelection(ValueError):
    pass


_WORD = r"[A-Za-z]+(?:['’-][A-Za-z]+)*"
_VALID_SELECTION = re.compile(rf"^{_WORD}(?:\s+{_WORD}){{0,4}}$")
_EDGE_PUNCTUATION = " \t\r\n\"“”‘’()[]{}<>.,;:!?，。；：！？、"


def normalize_selection(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidSelection("选区必须是文本")
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.strip(_EDGE_PUNCTUATION)
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized or len(normalized) > 120 or not _VALID_SELECTION.fullmatch(normalized):
        raise InvalidSelection("请选择 1–5 个英文单词")
    return normalized


def canonical_word(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).strip()).casefold()

