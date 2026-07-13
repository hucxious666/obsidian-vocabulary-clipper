import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clipper.dictionary import LookupNotFound
from clipper.dictionary_repository import DictionaryRepository
from clipper.dictionary_schema import create_pack_schema, write_pack_metadata


class DictionaryRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.dictionary_root = root / "dictionaries"
        self.dictionary_root.mkdir()
        self.catalog = root / "dictionary-catalog.json"
        self.catalog.write_text(json.dumps({
            "schemaVersion": 1,
            "packs": [
                {"id": "ecdict", "name": "ECDICT 完整字段版", "filename": "ecdict.sqlite3"},
                {"id": "kaikki-en", "name": "Kaikki English", "filename": "kaikki-en.sqlite3"},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        connection = sqlite3.connect(self.dictionary_root / "ecdict.sqlite3")
        create_pack_schema(connection)
        write_pack_metadata(connection, {"id": "ecdict", "name": "ECDICT 完整字段版"})
        connection.execute(
            "INSERT INTO entries(word, phonetic, translation) VALUES ('word', 'wɜːd', '单词')"
        )
        connection.commit()
        connection.close()
        self.repository = DictionaryRepository(self.dictionary_root, self.catalog)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_catalog_with_installed_state(self):
        self.assertEqual(
            [
                {"id": "ecdict", "name": "ECDICT 完整字段版", "installed": True},
                {"id": "kaikki-en", "name": "Kaikki English", "installed": False},
            ],
            self.repository.list_packs(),
        )

    def test_opens_only_installed_catalog_pack(self):
        self.assertEqual("单词", self.repository.lookup("ecdict", "word").translation)
        with self.assertRaisesRegex(LookupNotFound, "尚未安装"):
            self.repository.lookup("kaikki-en", "word")
        with self.assertRaisesRegex(LookupNotFound, "未知"):
            self.repository.lookup("unknown", "word")

    def test_rejects_database_with_wrong_pack_id(self):
        wrong = self.dictionary_root / "kaikki-en.sqlite3"
        connection = sqlite3.connect(wrong)
        create_pack_schema(connection)
        write_pack_metadata(connection, {"id": "other", "name": "Other"})
        connection.commit()
        connection.close()
        with self.assertRaisesRegex(LookupNotFound, "标识不匹配"):
            self.repository.lookup("kaikki-en", "word")


if __name__ == "__main__":
    unittest.main()
