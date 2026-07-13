from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TextIO

from .dictionary_schema import create_pack_schema, write_pack_metadata


def _open_source(path: Path) -> TextIO:
    if path.suffix.casefold() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _first_ipa(record: dict) -> str:
    for sound in record.get("sounds") or []:
        value = str(sound.get("ipa") or "").strip().strip("/[]")
        if value:
            return value
    return ""


def _upsert_entry(connection: sqlite3.Connection, record: dict) -> int:
    word = str(record.get("word") or "").strip()
    part = str(record.get("pos") or "").strip()
    row = connection.execute(
        "SELECT id, phonetic, pos, definition FROM entries WHERE word=? COLLATE NOCASE", (word,)
    ).fetchone()
    definitions = [
        str(gloss).strip()
        for sense in record.get("senses") or []
        for gloss in (sense.get("glosses") or [])[:1]
        if str(gloss).strip()
    ]
    if row:
        parts = [value for value in str(row[2] or "").split(",") if value]
        if part and part not in parts:
            parts.append(part)
        combined = "\n".join(filter(None, [str(row[3] or ""), *definitions]))
        connection.execute(
            "UPDATE entries SET phonetic=?, pos=?, definition=? WHERE id=?",
            (str(row[1] or "") or _first_ipa(record), ",".join(parts), combined, row[0]),
        )
        return int(row[0])
    cursor = connection.execute(
        "INSERT INTO entries(word, phonetic, definition, pos, metadata_json) VALUES (?, ?, ?, ?, ?)",
        (word, _first_ipa(record), "\n".join(definitions), part, '{"lang_code":"en"}'),
    )
    return int(cursor.lastrowid)


def _insert_senses(connection: sqlite3.Connection, entry_id: int, record: dict) -> None:
    row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) FROM senses WHERE entry_id=?", (entry_id,)
    ).fetchone()
    position = int(row[0]) + 1
    part = str(record.get("pos") or "").strip()
    for sense in record.get("senses") or []:
        glosses = [str(value).strip() for value in sense.get("glosses") or [] if str(value).strip()]
        if not glosses:
            continue
        tags = ",".join(str(value).strip() for value in sense.get("tags") or [] if str(value).strip())
        cursor = connection.execute(
            "INSERT INTO senses(entry_id, position, part_of_speech, gloss, tags) VALUES (?, ?, ?, ?, ?)",
            (entry_id, position, part, glosses[0], tags),
        )
        _insert_examples(connection, int(cursor.lastrowid), sense)
        position += 1


def _insert_examples(connection: sqlite3.Connection, sense_id: int, sense: dict) -> None:
    examples = []
    for example in sense.get("examples") or []:
        text = str(example.get("text") or "").strip()
        if text and example.get("type") != "quotation":
            examples.append((text, str(example.get("english") or "").strip()))
        if len(examples) == 3:
            break
    connection.executemany(
        "INSERT INTO examples(sense_id, position, text, translation) VALUES (?, ?, ?, ?)",
        [(sense_id, index, text, translation) for index, (text, translation) in enumerate(examples)],
    )


def _insert_forms(connection: sqlite3.Connection, word: str, record: dict) -> None:
    for form in record.get("forms") or []:
        value = str(form.get("form") or "").strip()
        if value and value != "-":
            connection.execute(
                "INSERT OR IGNORE INTO forms(form, lemma) VALUES (?, ?)", (value, word)
            )


def build_database(
    source_path: Path,
    database_path: Path,
    progress: Callable[[int], None] | None = None,
) -> int:
    source_path, database_path = Path(source_path), Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    processed = 0
    try:
        create_pack_schema(connection)
        write_pack_metadata(connection, {
            "id": "kaikki-en", "name": "Kaikki English", "source_language": "en",
            "target_language": "en", "source_format": "wiktextract_jsonl_gzip",
            "built_at": datetime.now(timezone.utc).isoformat(),
        })
        with _open_source(source_path) as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("lang_code") != "en" or not str(record.get("word") or "").strip():
                    continue
                entry_id = _upsert_entry(connection, record)
                _insert_senses(connection, entry_id, record)
                _insert_forms(connection, str(record["word"]).strip(), record)
                processed += 1
                if processed % 10_000 == 0:
                    connection.commit()
                    if progress:
                        progress(processed)
        connection.commit()
        count = int(connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0])
        connection.execute("PRAGMA optimize")
        connection.close()
        os.replace(temporary, database_path)
        return count
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m clipper.kaikki_builder <kaikki.jsonl.gz> <kaikki.sqlite3>", file=sys.stderr)
        return 2
    print(f"Imported {build_database(Path(args[0]), Path(args[1]))} dictionary entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
