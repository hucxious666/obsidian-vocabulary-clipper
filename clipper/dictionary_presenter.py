from __future__ import annotations

import re

from .dictionary import DictionaryEntry
from .meaning import normalize_ecdict_translation, parse_definition_groups


def _sense_groups(entry: DictionaryEntry) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    indexes: dict[str, int] = {}
    for sense in entry.senses:
        value = sense.translated_gloss or sense.gloss
        if not value:
            continue
        label = sense.part_of_speech or "释义"
        if label not in indexes:
            indexes[label] = len(groups)
            groups.append({"partOfSpeech": label, "definitions": []})
        groups[indexes[label]]["definitions"].append(value)
    return groups


def definition_groups(entry: DictionaryEntry) -> list[dict[str, object]]:
    groups = _sense_groups(entry)
    if groups:
        return groups
    groups = parse_definition_groups(entry.translation)
    if groups:
        return groups
    definitions = [
        re.sub(r"\s+", " ", line).strip()
        for line in str(entry.definition or "").replace("\\n", "\n").splitlines()
        if line.strip()
    ]
    return [{"partOfSpeech": entry.pos or "英文释义", "definitions": definitions}] if definitions else []


def english_groups(entry: DictionaryEntry) -> list[dict[str, object]]:
    if not entry.translation or not entry.definition:
        return []
    definitions = [
        re.sub(r"\s+", " ", line).strip()
        for line in str(entry.definition).replace("\\n", "\n").splitlines()
        if line.strip()
    ]
    return [{"partOfSpeech": "英文释义", "definitions": definitions}] if definitions else []


def markdown_meaning(entry: DictionaryEntry) -> str:
    translated = normalize_ecdict_translation(entry.translation)
    if translated:
        return translated
    parts = []
    for group in definition_groups(entry):
        prefix = str(group["partOfSpeech"] or "").strip()
        for index, value in enumerate(group["definitions"]):
            parts.append(f"{prefix}. {value}" if prefix and index == 0 else str(value))
    return "；".join(parts)


def definition_payload(entry: DictionaryEntry) -> dict[str, object]:
    allowed = {key: value for key, value in entry.metadata.items() if value and key in {
        "tag", "collins", "oxford", "bnc", "frq",
    }}
    return {
        "word": entry.matched_word,
        "phonetic": entry.phonetic,
        "source": entry.source_id,
        "sourceId": entry.source_id,
        "sourceName": entry.source_name,
        "groups": definition_groups(entry),
        "englishGroups": english_groups(entry),
        "examples": [
            {"text": example.text, "translation": example.translation}
            for example in entry.examples
        ],
        "metadata": allowed,
    }
