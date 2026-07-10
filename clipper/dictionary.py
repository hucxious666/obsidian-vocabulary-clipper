from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


class LookupNotFound(LookupError):
    pass


@dataclass(frozen=True)
class DictionaryEntry:
    matched_word: str
    phonetic: str
    translation: str


class DictionaryLookup:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    def lookup(self, word: str) -> DictionaryEntry:
        if not self.database_path.is_file():
            raise LookupNotFound("离线词典尚未安装")
        with closing(sqlite3.connect(self.database_path)) as connection:
            exact_row = connection.execute(
                "SELECT word, phonetic, translation FROM entries WHERE word = ? COLLATE NOCASE",
                (word,),
            ).fetchone()
            lemma_row = None
            if " " not in word:
                lemma = connection.execute(
                    "SELECT lemma FROM lemmas WHERE variant = ? COLLATE NOCASE", (word,)
                ).fetchone()
                if lemma:
                    lemma_row = connection.execute(
                        "SELECT word, phonetic, translation FROM entries WHERE word = ? COLLATE NOCASE",
                        (lemma[0],),
                    ).fetchone()
        row = exact_row or lemma_row
        if row is None or not str(row[1] or "").strip():
            raise LookupNotFound(f"词典中没有 {word} 的音标")
        phonetic = str((exact_row or lemma_row)[1] or "").strip().strip("/")
        translation_row = lemma_row if lemma_row and str(lemma_row[2] or "").strip() else row
        return DictionaryEntry(str(row[0]), phonetic, str(translation_row[2] or ""))
