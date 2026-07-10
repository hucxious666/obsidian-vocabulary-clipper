from __future__ import annotations

import re


_POS_ALIASES = {
    "a.": "adj.",
    "ad.": "adv.",
}
_POS_PATTERN = re.compile(
    r"^(adj\.|adv\.|prep\.|pron\.|conj\.|num\.|int\.|aux\.|vt\.|vi\.|n\.|v\.|a\.|ad\.)\s*",
    re.IGNORECASE,
)
_SEPARATOR_PATTERN = re.compile(r"\s*[,，;；]\s*")


def normalize_ecdict_translation(value: str) -> str:
    """Convert ECDICT's compact English notation into one Markdown-safe line."""
    output: list[str] = []
    seen_by_pos: dict[str, set[str]] = {}
    current_pos = ""
    source = str(value or "").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    for line in re.split(r"[\r\n]+", source):
        line = re.sub(r"\s+", " ", line).strip(" ;；,，。")
        if not line:
            continue
        pos_match = _POS_PATTERN.match(line)
        line_pos = ""
        if pos_match:
            source_pos = pos_match.group(1).casefold()
            current_pos = _POS_ALIASES.get(source_pos, source_pos)
            line_pos = current_pos
            line = line[pos_match.end() :]
        domain, line = _take_domain(line)
        meanings = [item.strip(" .。") for item in _SEPARATOR_PATTERN.split(line) if item.strip()]
        for index, meaning in enumerate(meanings):
            key = meaning.casefold()
            seen = seen_by_pos.setdefault(current_pos, set())
            if key in seen:
                continue
            seen.add(key)
            prefix = ""
            if index == 0:
                prefix = f"{line_pos}{domain}"
            output.append(f"{prefix}{meaning}")
    return "；".join(output)


def _take_domain(line: str) -> tuple[str, str]:
    match = re.match(r"^(\[[^\]]+\])\s*", line)
    if not match:
        return "", line
    return match.group(1), line[match.end() :]
