import tempfile
import unittest
from pathlib import Path

from clipper.config import AppConfig, ConfigStore
from clipper.dictionary import DictionaryEntry, LookupNotFound
from clipper.service import ClipperService
from clipper.translator import BaiduTranslateError
from clipper.youdao import YoudaoDictionaryResult


class MemoryProtector:
    def protect(self, value):
        return value[::-1]

    def unprotect(self, value):
        return value[::-1]


class FakeDictionary:
    def lookup(self, word):
        if word == "missing":
            raise LookupNotFound("missing")
        translations = {"word": "n. 单词, 词语", "fallback": ""}
        return DictionaryEntry(word, "wɜːd", translations.get(word, "v. 重复"))


class FakeTranslator:
    calls = []

    def translate(self, word):
        self.calls.append(word)
        return {"fallback": "百度兜底"}.get(word, "百度不应调用")


class FakeYoudao:
    def lookup(self, word):
        return YoudaoDictionaryResult(word, "wɜːd", ["n. 单词", "n. 词语"])


class ClipperServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.chapter = root / "chapters.md"
        self.news = root / "news.md"
        self.chapter.write_text("**chapter 22**\n\n", encoding="utf-8")
        self.news.write_text("*continue*\n\n33. old /oʊld/: <span class=\"meaning\">旧</span>\n", encoding="utf-8")
        self.store = ConfigStore(root / "config.json", MemoryProtector())
        self.store.save(
            AppConfig(
                str(self.chapter),
                str(self.news),
                22,
                "appid",
                "secret",
                "youdao-app",
                "youdao-secret",
            )
        )
        FakeTranslator.calls = []
        self.service = ClipperService(
            self.store,
            root / "dict.db",
            root / "backups",
            dictionary_factory=lambda _: FakeDictionary(),
            translator_factory=lambda _id, _key: FakeTranslator(),
            youdao_factory=lambda _id, _key: FakeYoudao(),
            file_picker=lambda _initial: str(self.news),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_entry_writes_only_configured_chapter_file(self):
        response = self.service.handle({"action": "add_entry", "target": "chapter", "text": "word"})
        self.assertEqual("added", response["status"])
        self.assertEqual(1, response["number"])
        self.assertIn("1. word /wɜːd/", self.chapter.read_text(encoding="utf-8"))
        self.assertIn("n.单词；词语", self.chapter.read_text(encoding="utf-8"))
        self.assertEqual([], FakeTranslator.calls)

    def test_baidu_is_only_used_when_ecdict_translation_is_empty(self):
        response = self.service.handle(
            {"action": "add_entry", "target": "chapter", "text": "fallback"}
        )
        self.assertEqual("added", response["status"])
        self.assertEqual(["fallback"], FakeTranslator.calls)
        self.assertIn("百度兜底", self.chapter.read_text(encoding="utf-8"))

    def test_youdao_dictionary_test_returns_preview_without_writing(self):
        before = self.chapter.read_bytes()
        response = self.service.handle(
            {"action": "test_youdao_dictionary", "text": "word"}
        )
        self.assertTrue(response["ok"])
        self.assertEqual("word", response["preview"]["word"])
        self.assertEqual(["n. 单词", "n. 词语"], response["preview"]["explains"])
        self.assertEqual(before, self.chapter.read_bytes())
        self.assertNotIn("youdao-secret", repr(response))

    def test_duplicate_is_reported_without_second_write(self):
        self.service.handle({"action": "add_entry", "target": "chapter", "text": "repeat"})
        self.service.dictionary_factory = lambda _: self.fail("duplicate should not query dictionary")
        response = self.service.handle({"action": "add_entry", "target": "chapter", "text": "Repeat"})
        self.assertEqual("duplicate", response["status"])
        self.assertEqual(1, self.chapter.read_text(encoding="utf-8").casefold().count("repeat /"))

    def test_lookup_failure_does_not_write_placeholder(self):
        before = self.news.read_bytes()
        response = self.service.handle({"action": "add_entry", "target": "news", "text": "missing"})
        self.assertEqual("lookup_failed", response["status"])
        self.assertEqual(before, self.news.read_bytes())

    def test_unknown_action_is_rejected(self):
        response = self.service.handle({"action": "write_any_file", "path": "C:\\secret.txt"})
        self.assertEqual("invalid", response["status"])

    def test_connection_maps_baidu_failure_to_lookup_failed(self):
        self.service.dictionary_path.write_bytes(b"placeholder")

        class FailingTranslator:
            def translate(self, _word):
                raise BaiduTranslateError("百度翻译错误 54001")

        self.service.translator_factory = lambda _id, _key: FailingTranslator()
        response = self.service.handle({"action": "test_connection"})
        self.assertEqual("lookup_failed", response["status"])

    def test_browse_file_returns_path_without_changing_configuration(self):
        response = self.service.handle({"action": "browse_file", "target": "news"})
        self.assertTrue(response["ok"])
        self.assertEqual(str(self.news), response["path"])
        self.assertEqual(str(self.chapter.resolve()), self.store.load().chapter_file)

    def test_youdao_credentials_must_be_updated_as_a_pair(self):
        response = self.service.handle(
            {
                "action": "save_settings",
                "chapterFile": str(self.chapter),
                "newsFile": str(self.news),
                "selectedChapter": 22,
                "youdaoAppKey": "new-key",
            }
        )
        self.assertEqual("invalid", response["status"])
        self.assertEqual("youdao-app", self.store.load().youdao_app_key)

    def test_youdao_credentials_can_be_replaced_without_being_returned(self):
        response = self.service.handle(
            {
                "action": "save_settings",
                "chapterFile": str(self.chapter),
                "newsFile": str(self.news),
                "selectedChapter": 22,
                "youdaoAppKey": "new-key",
                "youdaoSecretKey": "new-secret",
            }
        )
        self.assertTrue(response["ok"])
        self.assertNotIn("new-key", repr(response))
        self.assertNotIn("new-secret", repr(response))
        self.assertEqual("new-key", self.store.load().youdao_app_key)


if __name__ == "__main__":
    unittest.main()
