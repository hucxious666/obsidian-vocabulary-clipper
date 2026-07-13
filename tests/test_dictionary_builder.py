import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clipper.dictionary_builder import build_database


class DictionaryBuilderTests(unittest.TestCase):
    def test_imports_all_ecdict_fields_and_builds_lemma_map(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "ecdict.csv"
            db_path = Path(temp_dir) / "data" / "ecdict.sqlite3"
            fields = [
                "word", "phonetic", "definition", "translation", "pos", "collins",
                "oxford", "tag", "bnc", "frq", "exchange", "detail", "audio",
            ]
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "word": "run", "phonetic": "rʌn", "definition": "move quickly",
                    "translation": "vi. 跑", "pos": "v:90/n:10", "collins": "5",
                    "oxford": "1", "tag": "zk gk cet4", "bnc": "120", "frq": "98",
                    "exchange": "p:ran/i:running/3:runs", "detail": '{"source":"fixture"}',
                    "audio": "https://example.invalid/run.mp3",
                })
                writer.writerow({
                    "word": "running", "phonetic": "'rʌnɪŋ", "definition": "act of running",
                    "translation": "n. 跑步", "pos": "n:100", "exchange": "0:run",
                })

            count = build_database(csv_path, db_path)

            self.assertEqual(2, count)
            connection = sqlite3.connect(db_path)
            try:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
                self.assertIn("definition", columns)
                self.assertIn("metadata_json", columns)
                row = connection.execute(
                    "SELECT phonetic, definition, translation, pos, metadata_json "
                    "FROM entries WHERE word='run'"
                ).fetchone()
                self.assertEqual(("rʌn", "move quickly", "vi. 跑", "v:90/n:10"), row[:4])
                metadata = json.loads(row[4])
                self.assertEqual("5", metadata["collins"])
                self.assertEqual("1", metadata["oxford"])
                self.assertEqual("zk gk cet4", metadata["tag"])
                self.assertEqual("120", metadata["bnc"])
                self.assertEqual("98", metadata["frq"])
                self.assertEqual('{"source":"fixture"}', metadata["detail"])
                self.assertEqual("https://example.invalid/run.mp3", metadata["audio"])
                self.assertEqual(("run",), connection.execute(
                    "SELECT lemma FROM forms WHERE form='running'"
                ).fetchone())
                pack = dict(connection.execute("SELECT key, value FROM pack_metadata"))
                self.assertEqual("ecdict", pack["id"])
                self.assertEqual("1", pack["schema_version"])
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
