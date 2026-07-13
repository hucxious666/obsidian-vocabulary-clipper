from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from .dictionary_schema import read_pack_metadata


class LookupNotFound(LookupError):
    pass


@dataclass(frozen=True)
class DictionarySense:
    part_of_speech: str
    gloss: str
    translated_gloss: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DictionaryExample:
    text: str
    translation: str = ""
    sense_position: int = 0


@dataclass(frozen=True)
class DictionaryEntry:
    matched_word: str
    phonetic: str
    translation: str
    definition: str = ""
    source_id: str = "ecdict"
    source_name: str = "ECDICT"
    senses: tuple[DictionarySense, ...] = ()
    examples: tuple[DictionaryExample, ...] = ()
    pos: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class DictionaryLookup:
    _ENTRY_QUERY = (
        "SELECT id, word, phonetic, definition, translation, pos, metadata_json "
        "FROM entries WHERE word = ? COLLATE NOCASE"
    )

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    def lookup(self, word: str) -> DictionaryEntry:
        if not self.database_path.is_file():
            raise LookupNotFound("离线词典尚未安装")
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                exact = connection.execute(self._ENTRY_QUERY, (word,)).fetchone()
                lemma = self._lemma_entry(connection, word)
                displayed = exact or lemma
                meaning = self._meaning_entry(connection, exact, lemma)
                if displayed is None or meaning is None or not str(displayed[2] or "").strip():
                    raise LookupNotFound(f"词典中没有 {word} 的音标")
                senses = self._senses(connection, int(meaning[0]))
                examples = self._examples(connection, int(meaning[0]))
                pack = read_pack_metadata(connection)
        except sqlite3.DatabaseError as error:
            raise LookupNotFound("词典包已损坏") from error
        return DictionaryEntry(
            matched_word=str(displayed[1]),
            phonetic=str(displayed[2]).strip().strip("/[]"),
            translation=str(meaning[4] or ""),
            definition=str(meaning[3] or ""),
            source_id=pack.get("id", ""),
            source_name=pack.get("name", pack.get("id", "离线词典")),
            senses=senses,
            examples=examples,
            pos=str(meaning[5] or ""),
            metadata=self._metadata(meaning[6]),
        )

    def _lemma_entry(self, connection: sqlite3.Connection, word: str):
        if " " in word:
            return None
        form = connection.execute(
            "SELECT lemma FROM forms WHERE form = ? COLLATE NOCASE", (word,)
        ).fetchone()
        return connection.execute(self._ENTRY_QUERY, (form[0],)).fetchone() if form else None

    @staticmethod
    def _meaning_entry(connection: sqlite3.Connection, exact, lemma):
        if lemma:
            has_senses = connection.execute(
                "SELECT 1 FROM senses WHERE entry_id=? LIMIT 1", (lemma[0],)
            ).fetchone()
            if str(lemma[3] or "").strip() or str(lemma[4] or "").strip() or has_senses:
                return lemma
        return exact or lemma

    @staticmethod
    def _senses(connection: sqlite3.Connection, entry_id: int) -> tuple[DictionarySense, ...]:
        rows = connection.execute(
            "SELECT part_of_speech, gloss, translated_gloss, tags "
            "FROM senses WHERE entry_id=? ORDER BY position", (entry_id,)
        )
        return tuple(DictionarySense(
            str(row[0] or ""), str(row[1] or ""), str(row[2] or ""),
            tuple(value for value in str(row[3] or "").split(",") if value),
        ) for row in rows)

    @staticmethod
    def _examples(connection: sqlite3.Connection, entry_id: int) -> tuple[DictionaryExample, ...]:
        rows = connection.execute(
            "SELECT e.text, e.translation, s.position FROM examples e "
            "JOIN senses s ON s.id=e.sense_id WHERE s.entry_id=? ORDER BY s.position, e.position",
            (entry_id,),
        )
        return tuple(DictionaryExample(str(row[0]), str(row[1] or ""), int(row[2])) for row in rows)

    @staticmethod
    def _metadata(value: object) -> dict[str, str]:
        try:
            payload = json.loads(str(value or "{}"))
            return {str(key): str(item) for key, item in payload.items()}
        except (TypeError, ValueError):
            return {}
