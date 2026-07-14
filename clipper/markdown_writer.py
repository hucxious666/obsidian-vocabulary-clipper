from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .entry import format_entry
from .selection import canonical_word
from .sections import (
    find_chapters,
    find_sections,
    normalize_section_name,
    section_headings,
)


class DuplicateEntry(ValueError): pass


class ChapterNotFound(ValueError): pass


class SectionNotFound(ValueError): pass


class ConcurrentWriteError(OSError): pass


@dataclass(frozen=True)
class WriteResult:
    number: int
    target: str


_ENTRY = re.compile(r"^[ \t]*(?:-[ \t]*)?(\d+)\.[ \t]+(.+?)[ \t]+/[^/\r\n]+/", re.MULTILINE)
_THEMATIC_BREAK = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)


def _newline_for(source: str) -> str:
    return "\r\n" if "\r\n" in source else "\n"


def _entry_words(source: str) -> set[str]:
    return {canonical_word(match.group(2)) for match in _ENTRY.finditer(source)}


def _append_to_chapter_region(region: str, entry: str, newline: str) -> str:
    stripped_end = region.rstrip(" \t\r\n")
    separator_start = None
    matches = list(_THEMATIC_BREAK.finditer(stripped_end))
    if matches and matches[-1].end() == len(stripped_end):
        separator_start = matches[-1].start()

    if separator_start is None:
        body = stripped_end
        suffix = ""
    else:
        body = stripped_end[:separator_start].rstrip(" \t\r\n")
        suffix = stripped_end[separator_start:]

    if body.strip():
        result = body + newline + entry
    else:
        result = newline * 2 + entry
    if suffix:
        result += newline * 2 + suffix
    if region.endswith(("\n", "\r")):
        result += newline
    return result


def insert_section_entry(
    source: str,
    section: str,
    word: str,
    phonetic: str,
    meaning: str,
    meaning_style: str = "covered",
) -> tuple[str, int]:
    name = normalize_section_name(section)
    headings = section_headings(source)
    matches = [heading for heading in headings if heading.name.casefold() == name.casefold()]
    if len(matches) > 1:
        raise ValueError(f"章节名称重复：{name}")
    for heading in matches:
        index = headings.index(heading)
        end = headings[index + 1].start if index + 1 < len(headings) else len(source)
        region = source[heading.end:end]
        if canonical_word(word) in _entry_words(region):
            raise DuplicateEntry(f"{word} 已存在于 {name}")
        numbers = [int(match.group(1)) for match in _ENTRY.finditer(region)]
        number = max(numbers, default=0) + 1
        updated_region = _append_to_chapter_region(
            region,
            format_entry(number, word, phonetic=phonetic, meaning=meaning, meaning_style=meaning_style),
            _newline_for(source),
        )
        return source[:heading.end] + updated_region + source[end:], number
    raise SectionNotFound(f"未找到章节：{name}")


def insert_chapter_entry(
    source: str,
    chapter: int,
    word: str,
    phonetic: str,
    meaning: str,
    meaning_style: str = "covered",
) -> tuple[str, int]:
    return insert_section_entry(
        source, f"Chapter {int(chapter)}", word, phonetic, meaning, meaning_style
    )


def create_section(source: str, section: str) -> tuple[str, str]:
    name = normalize_section_name(section)
    if any(existing.casefold() == name.casefold() for existing in find_sections(source)):
        raise ValueError(f"章节已存在：{name}")
    newline = _newline_for(source)
    prefix = source.rstrip(" \t\r\n")
    separator = newline * 2 if prefix else ""
    return f"{prefix}{separator}## {name}{newline}", name


def _tail_number(source: str) -> int:
    lines = source.splitlines()
    index = len(lines) - 1
    while index >= 0 and not lines[index].strip():
        index -= 1
    numbers: list[int] = []
    while index >= 0:
        match = re.match(r"^[ \t]*(?:-[ \t]*)?(\d+)\.", lines[index])
        if not match:
            break
        numbers.append(int(match.group(1)))
        index -= 1
        while index >= 0 and not lines[index].strip():
            index -= 1
    return max(numbers, default=0)


def insert_news_entry(
    source: str,
    word: str,
    phonetic: str,
    meaning: str,
    meaning_style: str = "covered",
) -> tuple[str, int]:
    if canonical_word(word) in _entry_words(source):
        raise DuplicateEntry(f"{word} 已存在于笔记")
    number = _tail_number(source) + 1
    newline = _newline_for(source)
    entry = format_entry(number, word, phonetic=phonetic, meaning=meaning, meaning_style=meaning_style)
    if not source.strip():
        return entry + newline, number
    updated = source.rstrip(" \t\r\n") + newline + entry
    if source.endswith(("\n", "\r")):
        updated += newline
    return updated, number


def _read_text(path: Path) -> tuple[bytes, str, bool]:
    data = path.read_bytes()
    has_bom = data.startswith(b"\xef\xbb\xbf")
    return data, data.decode("utf-8-sig" if has_bom else "utf-8"), has_bom


def ensure_not_duplicate(path: Path, target: str, section: str | int | None, word: str) -> None:
    _, source, _ = _read_text(Path(path))
    region = source
    if target in {"chapter", "section"}:
        name = f"Chapter {int(section or 0)}" if target == "chapter" else str(section or "")
        headings = section_headings(source)
        matches = [heading for heading in headings if heading.name.casefold() == name.casefold()]
        if len(matches) != 1:
            raise SectionNotFound(f"未找到唯一章节：{name}")
        index = headings.index(matches[0])
        end = headings[index + 1].start if index + 1 < len(headings) else len(source)
        region = source[matches[0].end:end]
    if canonical_word(word) in _entry_words(region):
        label = str(section) if target in {"chapter", "section"} else "笔记末尾"
        raise DuplicateEntry(f"{word} 已存在于 {label}")


def _backup_file(path: Path, backup_root: Path) -> None:
    bucket = hashlib.sha256(str(path.resolve()).casefold().encode("utf-8")).hexdigest()[:16]
    directory = backup_root / bucket
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    shutil.copy2(path, directory / f"{stamp}-{path.name}")
    backups = sorted(directory.glob(f"*-{path.name}"), reverse=True)
    for stale in backups[10:]:
        stale.unlink(missing_ok=True)


def _write_temporary(path: Path, encoded: bytes) -> str:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        return handle.name


def restore_bytes_atomic(path: Path, data: bytes) -> None:
    temp_name = _write_temporary(path, data)
    try:
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _transform_atomic(
    path: Path, backup_root: Path, transform: Callable[[str], tuple[str, WriteResult]]
) -> WriteResult:
    path = path.resolve()
    for attempt in range(2):
        before = path.stat()
        _, source, has_bom = _read_text(path)
        updated, result = transform(source)
        current = path.stat()
        if (current.st_mtime_ns, current.st_size) != (before.st_mtime_ns, before.st_size):
            if attempt == 0:
                continue
            raise ConcurrentWriteError("文件在写入期间被修改")

        _backup_file(path, backup_root)
        encoded = updated.encode("utf-8")
        if has_bom:
            encoded = b"\xef\xbb\xbf" + encoded
        temp_name = None
        conflict_after_backup = False
        try:
            temp_name = _write_temporary(path, encoded)
            latest = path.stat()
            if (latest.st_mtime_ns, latest.st_size) != (before.st_mtime_ns, before.st_size):
                conflict_after_backup = True
            else:
                os.replace(temp_name, path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
        if conflict_after_backup:
            if attempt == 0:
                continue
            raise ConcurrentWriteError("文件在写入期间被修改")
        return result
    raise ConcurrentWriteError("文件在写入期间被修改")


def write_entry_atomic(
    path: Path,
    target: str,
    section: str | int | None,
    word: str,
    phonetic: str,
    meaning: str,
    backup_root: Path,
    meaning_style: str = "covered",
) -> WriteResult:
    def transform(source: str) -> tuple[str, WriteResult]:
        if target in {"chapter", "section"}:
            name = f"Chapter {int(section or 0)}" if target == "chapter" else str(section or "")
            updated, number = insert_section_entry(
                source, name, word, phonetic, meaning, meaning_style
            )
        elif target in {"news", "append"}:
            updated, number = insert_news_entry(source, word, phonetic, meaning, meaning_style)
        else:
            raise ValueError("未知写入目标")
        return updated, WriteResult(number=number, target=target)

    return _transform_atomic(path, backup_root, transform)


def create_section_atomic(
    path: Path,
    section: str,
    backup_root: Path,
    entry: tuple[str, str, str, str] | None = None,
) -> WriteResult:
    name = normalize_section_name(section)

    def transform(source: str) -> tuple[str, WriteResult]:
        updated, _ = create_section(source, name)
        number = 0
        if entry:
            updated, number = insert_section_entry(updated, name, *entry)
        return updated, WriteResult(number=number, target="section")

    return _transform_atomic(path, backup_root, transform)
