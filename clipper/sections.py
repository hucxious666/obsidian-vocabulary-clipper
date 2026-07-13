from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionHeading:
    name: str
    start: int
    end: int


_H2_HEADING = re.compile(r"^[ \t]{0,3}##(?!#)[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_LEGACY_CHAPTER = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*|\*{1,2}[ \t]*)chapter[ \t]+(\d+)[ \t]*\*{0,2}[ \t]*$",
    re.IGNORECASE,
)
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


def normalize_section_name(value: str) -> str:
    raw = str(value)
    if "\r" in raw or "\n" in raw:
        raise ValueError("章节名称不能包含换行")
    name = " ".join(raw.split())
    if not name:
        raise ValueError("章节名称不能为空")
    if len(name) > 80:
        raise ValueError("章节名称不能超过 80 个字符")
    legacy = re.fullmatch(r"chapter[ \t]+(\d+)", name, re.IGNORECASE)
    return f"Chapter {int(legacy.group(1))}" if legacy else name


def section_headings(source: str) -> list[SectionHeading]:
    headings: list[SectionHeading] = []
    offset = 0
    fence: tuple[str, int] | None = None
    for line_with_end in source.splitlines(keepends=True):
        line = line_with_end.rstrip("\r\n")
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            offset += len(line_with_end)
            continue
        if fence is None:
            h2 = _H2_HEADING.match(line)
            legacy = _LEGACY_CHAPTER.match(line)
            if h2:
                headings.append(
                    SectionHeading(normalize_section_name(h2.group(1)), offset, offset + len(line))
                )
            elif legacy:
                headings.append(
                    SectionHeading(f"Chapter {int(legacy.group(1))}", offset, offset + len(line))
                )
        offset += len(line_with_end)
    return headings


def find_sections(source: str) -> list[str]:
    sections: list[str] = []
    seen: set[str] = set()
    for heading in section_headings(source):
        key = heading.name.casefold()
        if key not in seen:
            seen.add(key)
            sections.append(heading.name)
    return sections


def find_chapters(source: str) -> list[int]:
    chapters: list[int] = []
    for name in find_sections(source):
        match = re.fullmatch(r"Chapter (\d+)", name)
        if match:
            chapters.append(int(match.group(1)))
    return chapters
