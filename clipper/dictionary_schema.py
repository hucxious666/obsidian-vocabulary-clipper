from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Mapping


SCHEMA_VERSION = 1
REQUIRED_TABLES = {"pack_metadata", "entries", "senses", "examples", "forms"}


class PackValidationError(ValueError):
    pass


def create_pack_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE pack_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL COLLATE NOCASE UNIQUE,
            phonetic TEXT NOT NULL DEFAULT '',
            definition TEXT NOT NULL DEFAULT '',
            translation TEXT NOT NULL DEFAULT '',
            pos TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE senses (
            id INTEGER PRIMARY KEY,
            entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            part_of_speech TEXT NOT NULL DEFAULT '',
            gloss TEXT NOT NULL DEFAULT '',
            translated_gloss TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            UNIQUE(entry_id, position)
        );
        CREATE TABLE examples (
            id INTEGER PRIMARY KEY,
            sense_id INTEGER NOT NULL REFERENCES senses(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            text TEXT NOT NULL,
            translation TEXT NOT NULL DEFAULT '',
            UNIQUE(sense_id, position)
        );
        CREATE TABLE forms (
            form TEXT PRIMARY KEY COLLATE NOCASE,
            lemma TEXT NOT NULL COLLATE NOCASE
        );
        CREATE INDEX senses_entry_idx ON senses(entry_id, position);
        CREATE INDEX examples_sense_idx ON examples(sense_id, position);
        """
    )


def write_pack_metadata(connection: sqlite3.Connection, values: Mapping[str, object]) -> None:
    payload = {"schema_version": str(SCHEMA_VERSION), **{key: str(value) for key, value in values.items()}}
    connection.executemany(
        "INSERT OR REPLACE INTO pack_metadata(key, value) VALUES (?, ?)", payload.items()
    )


def read_pack_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    return dict(connection.execute("SELECT key, value FROM pack_metadata"))


def validate_pack(path: Path, expected_id: str | None = None) -> dict[str, str]:
    path = Path(path)
    if not path.is_file():
        raise PackValidationError("离线词典尚未安装")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not REQUIRED_TABLES.issubset(tables):
            raise PackValidationError("词典包结构不完整")
        metadata = read_pack_metadata(connection)
        connection.close()
    except sqlite3.DatabaseError as error:
        raise PackValidationError("词典包已损坏") from error
    if metadata.get("schema_version") != str(SCHEMA_VERSION):
        raise PackValidationError("词典包版本不兼容")
    if expected_id and metadata.get("id") != expected_id:
        raise PackValidationError("词典包标识不匹配")
    if not metadata.get("id") or not metadata.get("name"):
        raise PackValidationError("词典包元数据不完整")
    return metadata
