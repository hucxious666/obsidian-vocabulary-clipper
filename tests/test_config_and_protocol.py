import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from clipper.config import AppConfig, ConfigStore, SettingsValidationError
from clipper.protocol import read_message, write_message


class MemoryProtector:
    def protect(self, value):
        return "protected:" + value[::-1]

    def unprotect(self, value):
        return value.removeprefix("protected:")[::-1]


class ConfigStoreTests(unittest.TestCase):
    def test_saves_and_exposes_named_section_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            section = Path(temp_dir) / "sections.md"
            append = Path(temp_dir) / "append.md"
            section.write_text("## 阅读\n\n## Match Review\n", encoding="utf-8")
            append.write_text("", encoding="utf-8")
            store = ConfigStore(Path(temp_dir) / "config.json", MemoryProtector())

            store.save(
                AppConfig(
                    str(section), str(append), "Match Review", "appid", "secret"
                )
            )
            config = store.load()
            public = store.public_settings()

            self.assertEqual(str(section.resolve()), config.section_file)
            self.assertEqual(str(append.resolve()), config.append_file)
            self.assertEqual("Match Review", config.selected_section)
            self.assertEqual(["阅读", "Match Review"], public["sections"])
            self.assertEqual("Match Review", public["selectedSection"])
            self.assertEqual(str(section.resolve()), public["sectionFile"])
            self.assertEqual(str(append.resolve()), public["appendFile"])
            self.assertEqual("ecdict", config.dictionary_id)
            self.assertEqual("ecdict", public["activeDictionary"])

    def test_persists_selected_dictionary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            section = Path(temp_dir) / "sections.md"
            append = Path(temp_dir) / "append.md"
            section.write_text("## 阅读\n", encoding="utf-8")
            append.write_text("", encoding="utf-8")
            store = ConfigStore(Path(temp_dir) / "config.json", MemoryProtector())

            store.save(AppConfig(
                str(section), str(append), "阅读", "appid", "secret",
                dictionary_id="kaikki-en",
            ))

            self.assertEqual("kaikki-en", store.load().dictionary_id)
            self.assertEqual("kaikki-en", store.public_settings()["activeDictionary"])

    def test_credentials_are_protected_and_never_returned_in_public_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chapter = Path(temp_dir) / "chapter.md"
            news = Path(temp_dir) / "news.md"
            chapter.write_text("**chapter 22**\n", encoding="utf-8")
            news.write_text("", encoding="utf-8")
            store = ConfigStore(Path(temp_dir) / "config.json", MemoryProtector())
            store.save(
                AppConfig(
                    str(chapter), str(news), 22, "appid", "secret", "youdao-app", "youdao-secret"
                )
            )

            raw = (Path(temp_dir) / "config.json").read_text(encoding="utf-8")
            public = store.public_settings()

            self.assertNotIn("secret", raw)
            self.assertNotIn("appid", json.dumps(public))
            self.assertNotIn("youdao-app", raw)
            self.assertNotIn("youdao-secret", raw)
            self.assertTrue(public["credentialsConfigured"])
            self.assertTrue(public["youdaoCredentialsConfigured"])

    def test_loads_legacy_config_without_youdao_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chapter = Path(temp_dir) / "chapter.md"
            news = Path(temp_dir) / "news.md"
            chapter.write_text("**chapter 22**\n", encoding="utf-8")
            news.write_text("", encoding="utf-8")
            path = Path(temp_dir) / "config.json"
            protector = MemoryProtector()
            path.write_text(
                json.dumps(
                    {
                        "chapter_file": str(chapter),
                        "news_file": str(news),
                        "selected_chapter": 22,
                        "credentials": {
                            "id": protector.protect("appid"),
                            "key": protector.protect("secret"),
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = ConfigStore(path, protector).load()
            self.assertEqual(str(chapter.resolve()), config.section_file)
            self.assertEqual(str(news.resolve()), config.append_file)
            self.assertEqual("Chapter 22", config.selected_section)
            self.assertEqual("", config.youdao_app_key)
            self.assertEqual("", config.youdao_secret_key)
            self.assertEqual("ecdict", config.dictionary_id)

    def test_rejects_non_markdown_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            text_file = Path(temp_dir) / "words.txt"
            text_file.write_text("", encoding="utf-8")
            store = ConfigStore(Path(temp_dir) / "config.json", MemoryProtector())
            with self.assertRaises(SettingsValidationError):
                store.validate_path(text_file)


class ProtocolTests(unittest.TestCase):
    def test_round_trips_utf8_native_message(self):
        stream = io.BytesIO()
        write_message(stream, {"message": "中文"})
        stream.seek(0)
        self.assertEqual({"message": "中文"}, read_message(stream))

    def test_rejects_oversized_message_before_reading_payload(self):
        stream = io.BytesIO(struct.pack("<I", 1_048_577))
        with self.assertRaises(ValueError):
            read_message(stream)


if __name__ == "__main__":
    unittest.main()
