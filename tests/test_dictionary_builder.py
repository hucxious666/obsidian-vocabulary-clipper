import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clipper.dictionary_builder import build_database


class DictionaryBuilderTests(unittest.TestCase):
    def test_imports_required_fields_and_builds_lemma_map(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "ecdict.csv"
            db_path = Path(temp_dir) / "data" / "ecdict.sqlite3"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["word", "phonetic", "translation", "exchange"])
                writer.writeheader()
                writer.writerow({"word": "run", "phonetic": "rʌn", "translation": "跑", "exchange": "p:ran/i:running/3:runs"})
                writer.writerow({"word": "running", "phonetic": "'rʌnɪŋ", "translation": "跑步", "exchange": "0:run"})

            count = build_database(csv_path, db_path)

            self.assertEqual(2, count)
            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(("rʌn",), connection.execute("SELECT phonetic FROM entries WHERE word='run'").fetchone())
                self.assertEqual(("run",), connection.execute("SELECT lemma FROM lemmas WHERE variant='running'").fetchone())
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
