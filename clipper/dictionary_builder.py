from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .dictionary_schema import create_pack_schema, write_pack_metadata


_VARIANT_CODES = {"p", "d", "i", "3", "r", "t", "s"}


def _exchange_pairs(word: str, exchange: str):
    for item in (exchange or "").split("/"):
        if ":" not in item:
            continue
        code, value = item.split(":", 1)
        value = value.strip()
        if not value:
            continue
        if code == "0":
            yield word, value
        elif code in _VARIANT_CODES:
            for variant in value.split(","):
                if variant.strip():
                    yield variant.strip(), word


_METADATA_FIELDS = ("collins", "oxford", "tag", "bnc", "frq", "exchange", "detail", "audio")


def _entry_values(row: dict[str, str]) -> tuple[str, ...]:
    metadata = {field: (row.get(field) or "").strip() for field in _METADATA_FIELDS}
    return (
        (row.get("word") or "").strip(),
        (row.get("phonetic") or "").strip(),
        (row.get("definition") or "").strip(),
        (row.get("translation") or "").strip(),
        (row.get("pos") or "").strip(),
        json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    )


def _insert_row(connection: sqlite3.Connection, row: dict[str, str]) -> bool:
    values = _entry_values(row)
    if not values[0]:
        return False
    connection.execute(
        "INSERT OR REPLACE INTO entries"
        "(word, phonetic, definition, translation, pos, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
        values,
    )
    for variant, lemma in _exchange_pairs(values[0], row.get("exchange") or ""):
        connection.execute(
            "INSERT OR IGNORE INTO forms(form, lemma) VALUES (?, ?)", (variant, lemma)
        )
    return True


def build_database(csv_path: Path, database_path: Path) -> int:
    csv_path = Path(csv_path)
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    count = 0
    try:
        create_pack_schema(connection)
        write_pack_metadata(connection, {
            "id": "ecdict",
            "name": "ECDICT 完整字段版",
            "source_language": "en",
            "target_language": "zh-Hans",
            "source_format": "ecdict_csv",
            "built_at": datetime.now(timezone.utc).isoformat(),
        })
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not _insert_row(connection, row):
                    continue
                count += 1
                if count % 20_000 == 0:
                    connection.commit()
        connection.commit()
        connection.execute("PRAGMA optimize")
        connection.close()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, database_path)
        return count
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m clipper.dictionary_builder <ecdict.csv> <ecdict.sqlite3>", file=sys.stderr)
        return 2
    count = build_database(Path(args[0]), Path(args[1]))
    print(f"Imported {count} dictionary entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
