from __future__ import annotations

import csv
import os
import sqlite3
import sys
from pathlib import Path


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


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE entries (
            word TEXT PRIMARY KEY COLLATE NOCASE,
            phonetic TEXT NOT NULL,
            translation TEXT NOT NULL
        );
        CREATE TABLE lemmas (
            variant TEXT PRIMARY KEY COLLATE NOCASE,
            lemma TEXT NOT NULL
        );
        """
    )


def build_database(csv_path: Path, database_path: Path) -> int:
    csv_path = Path(csv_path)
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    count = 0
    try:
        _create_schema(connection)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                word = (row.get("word") or "").strip()
                if not word:
                    continue
                connection.execute(
                    "INSERT OR REPLACE INTO entries(word, phonetic, translation) VALUES (?, ?, ?)",
                    (word, (row.get("phonetic") or "").strip(), (row.get("translation") or "").strip()),
                )
                for variant, lemma in _exchange_pairs(word, row.get("exchange") or ""):
                    connection.execute(
                        "INSERT OR IGNORE INTO lemmas(variant, lemma) VALUES (?, ?)", (variant, lemma)
                    )
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
