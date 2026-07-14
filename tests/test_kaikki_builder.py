import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clipper.kaikki_builder import build_database


class KaikkiBuilderTests(unittest.TestCase):
    def test_imports_english_senses_pronunciation_examples_and_forms(self):
        records = [
            {
                "word": "run",
                "lang_code": "en",
                "pos": "verb",
                "sounds": [{"ipa": "/rʌn/", "tags": ["UK"]}],
                "forms": [
                    {"form": "runs", "tags": ["third-person", "singular"]},
                    {"form": "running", "tags": ["participle"]},
                ],
                "senses": [
                    {
                        "glosses": ["To move swiftly on foot."],
                        "tags": ["intransitive"],
                        "examples": [
                            {"text": "She runs every morning.", "type": "example"},
                            {"text": "A long literary quotation.", "type": "quotation"},
                        ],
                    },
                    {"glosses": ["To flow."], "examples": [{"text": "The river runs south."}]},
                ],
            },
            {
                "word": "run",
                "lang_code": "en",
                "pos": "noun",
                "senses": [{"glosses": ["An act of running."]}],
            },
            {
                "word": "maison",
                "lang_code": "fr",
                "pos": "noun",
                "senses": [{"glosses": ["house"]}],
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "kaikki.jsonl.gz"
            target = Path(temp_dir) / "kaikki-en.sqlite3"
            with gzip.open(source, "wt", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")

            count = build_database(source, target)

            self.assertEqual(1, count)
            connection = sqlite3.connect(target)
            try:
                entry = connection.execute(
                    "SELECT word, phonetic, pos FROM entries"
                ).fetchone()
                self.assertEqual(("run", "rʌn", "verb,noun"), entry)
                senses = connection.execute(
                    "SELECT part_of_speech, gloss, tags FROM senses ORDER BY position"
                ).fetchall()
                self.assertEqual(
                    [
                        ("verb", "To move swiftly on foot.", "intransitive"),
                        ("verb", "To flow.", ""),
                        ("noun", "An act of running.", ""),
                    ],
                    senses,
                )
                self.assertEqual(
                    [("She runs every morning.",), ("The river runs south.",)],
                    connection.execute("SELECT text FROM examples ORDER BY id").fetchall(),
                )
                self.assertEqual(("run",), connection.execute(
                    "SELECT lemma FROM forms WHERE form='running'"
                ).fetchone())
                metadata = dict(connection.execute("SELECT key, value FROM pack_metadata"))
                self.assertEqual("kaikki-en", metadata["id"])
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
