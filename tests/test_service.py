import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clipper.config import AppConfig, ConfigStore
from clipper.dictionary import DictionaryEntry, LookupNotFound
from clipper.service import ClipperService
from clipper.translator import BaiduTranslateError
from clipper.youdao import YoudaoTranslateError


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
        return {
            "fallback": "百度兜底",
            "Liverpool are playing well.": "利物浦踢得很好。",
        }.get(word, "百度不应调用")


class FakeYoudao:
    calls = []

    def translate(self, text):
        self.calls.append(text)
        return "有道翻译结果"


class ClipperServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.chapter = root / "chapters.md"
        self.news = root / "news.md"
        self.chapter.write_text("**chapter 22**\n\n## 阅读\n\n", encoding="utf-8")
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
        FakeYoudao.calls = []
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

    def test_add_entry_can_target_named_section(self):
        response = self.service.handle(
            {
                "action": "add_entry",
                "target": "section",
                "sectionName": "阅读",
                "text": "word",
            }
        )

        self.assertEqual("added", response["status"])
        self.assertEqual("阅读", response["targetLabel"])
        reading = self.chapter.read_text(encoding="utf-8").split("## 阅读", 1)[1]
        self.assertIn("1. word /wɜːd/", reading)

    def test_select_section_updates_default(self):
        response = self.service.handle(
            {"action": "select_section", "sectionName": "阅读"}
        )

        self.assertTrue(response["ok"])
        self.assertEqual("阅读", self.store.load().selected_section)
        self.assertEqual("阅读", response["selectedSection"])

    def test_create_section_appends_h2_and_selects_it(self):
        response = self.service.handle(
            {"action": "create_section", "sectionName": "  Match   Review  "}
        )

        self.assertTrue(response["ok"])
        self.assertEqual("Match Review", self.store.load().selected_section)
        self.assertTrue(self.chapter.read_text(encoding="utf-8").endswith("## Match Review\n"))

    def test_create_section_and_add_entry_is_one_operation(self):
        response = self.service.handle(
            {
                "action": "create_section_and_add_entry",
                "sectionName": "比赛",
                "text": "word",
            }
        )

        self.assertTrue(response["ok"])
        self.assertEqual("比赛", response["targetLabel"])
        self.assertEqual("比赛", self.store.load().selected_section)
        created = self.chapter.read_text(encoding="utf-8").split("## 比赛", 1)[1]
        self.assertIn("1. word /wɜːd/", created)

    def test_create_section_rolls_back_note_when_config_save_fails(self):
        before = self.chapter.read_bytes()

        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            response = self.service.handle(
                {"action": "create_section", "sectionName": "不应残留"}
            )

        self.assertEqual("write_failed", response["status"])
        self.assertEqual(before, self.chapter.read_bytes())

    def test_append_target_writes_to_append_note(self):
        response = self.service.handle(
            {"action": "add_entry", "target": "append", "text": "word"}
        )

        self.assertTrue(response["ok"])
        self.assertEqual("笔记末尾", response["targetLabel"])
        self.assertIn("34. word /wɜːd/", self.news.read_text(encoding="utf-8"))

    def test_plain_style_applies_to_section_append_and_create_section(self):
        section_response = self.service.handle(
            {
                "action": "add_entry",
                "target": "section",
                "sectionName": "阅读",
                "text": "word",
                "meaningStyle": "plain",
            }
        )
        append_response = self.service.handle(
            {
                "action": "add_entry",
                "target": "append",
                "text": "fallback",
                "meaningStyle": "plain",
            }
        )
        create_response = self.service.handle(
            {
                "action": "create_section_and_add_entry",
                "sectionName": "明文章节",
                "text": "repeat",
                "meaningStyle": "plain",
            }
        )

        self.assertEqual("plain", section_response["meaningStyle"])
        self.assertEqual("plain", append_response["meaningStyle"])
        self.assertEqual("plain", create_response["meaningStyle"])
        self.assertIn("1. word /wɜːd/: n.单词；词语", self.chapter.read_text(encoding="utf-8"))
        self.assertIn("34. fallback /", self.news.read_text(encoding="utf-8"))
        self.assertNotIn('<span class="meaning">百度兜底</span>', self.news.read_text(encoding="utf-8"))
        created = self.chapter.read_text(encoding="utf-8").split("## 明文章节", 1)[1]
        self.assertNotIn('<span class="meaning">', created)

    def test_missing_style_defaults_to_covered_and_invalid_style_does_not_write(self):
        covered = self.service.handle(
            {"action": "add_entry", "target": "section", "sectionName": "阅读", "text": "word"}
        )
        before = self.news.read_bytes()
        invalid = self.service.handle(
            {
                "action": "add_entry",
                "target": "append",
                "text": "fallback",
                "meaningStyle": "unexpected",
            }
        )

        self.assertEqual("covered", covered["meaningStyle"])
        self.assertIn('<span class="meaning">', self.chapter.read_text(encoding="utf-8"))
        self.assertEqual("invalid", invalid["status"])
        self.assertEqual(before, self.news.read_bytes())

    def test_baidu_is_only_used_when_ecdict_translation_is_empty(self):
        response = self.service.handle(
            {"action": "add_entry", "target": "chapter", "text": "fallback"}
        )
        self.assertEqual("added", response["status"])
        self.assertEqual(["fallback"], FakeTranslator.calls)
        self.assertIn("百度兜底", self.chapter.read_text(encoding="utf-8"))

    def test_lookup_definition_returns_grouped_details_without_writing(self):
        chapter_before = self.chapter.read_bytes()
        news_before = self.news.read_bytes()

        response = self.service.handle(
            {"action": "lookup_definition", "text": "word"}
        )

        self.assertTrue(response["ok"])
        self.assertEqual("ok", response["status"])
        self.assertEqual(
            {
                "word": "word",
                "phonetic": "wɜːd",
                "source": "ecdict",
                "groups": [
                    {"partOfSpeech": "n.", "definitions": ["单词", "词语"]}
                ],
            },
            response["definition"],
        )
        self.assertEqual(chapter_before, self.chapter.read_bytes())
        self.assertEqual(news_before, self.news.read_bytes())
        self.assertEqual([], FakeTranslator.calls)

    def test_lookup_definition_uses_baidu_only_when_ecdict_meaning_is_empty(self):
        response = self.service.handle(
            {"action": "lookup_definition", "text": "fallback"}
        )

        self.assertTrue(response["ok"])
        self.assertEqual("baidu", response["definition"]["source"])
        self.assertEqual(
            [{"partOfSpeech": "释义", "definitions": ["百度兜底"]}],
            response["definition"]["groups"],
        )
        self.assertEqual(["fallback"], FakeTranslator.calls)

    def test_translate_selection_uses_baidu_without_writing(self):
        chapter_before = self.chapter.read_bytes()
        news_before = self.news.read_bytes()
        response = self.service.handle(
            {"action": "translate_selection", "text": "Liverpool are playing well."}
        )
        self.assertEqual(
            {
                "sourceText": "Liverpool are playing well.",
                "translatedText": "利物浦踢得很好。",
                "source": "baidu",
            },
            response["translation"],
        )
        self.assertEqual([], FakeYoudao.calls)
        self.assertEqual(chapter_before, self.chapter.read_bytes())
        self.assertEqual(news_before, self.news.read_bytes())

    def test_translate_selection_falls_back_to_youdao(self):
        class FailingBaidu:
            def translate(self, _text):
                raise BaiduTranslateError("百度翻译错误 54003")

        self.service.translator_factory = lambda _id, _key: FailingBaidu()
        response = self.service.handle(
            {"action": "translate_selection", "text": "Liverpool are playing well."}
        )
        self.assertEqual("有道翻译结果", response["translation"]["translatedText"])
        self.assertEqual("youdao", response["translation"]["source"])
        self.assertEqual(["Liverpool are playing well."], FakeYoudao.calls)

    def test_translate_selection_reports_missing_youdao_fallback(self):
        config = self.store.load()
        self.store.save(AppConfig(
            config.chapter_file, config.news_file, config.selected_chapter,
            config.app_id, config.secret_key,
        ))

        class FailingBaidu:
            def translate(self, _text):
                raise BaiduTranslateError("百度翻译错误 54003")

        self.service.translator_factory = lambda _id, _key: FailingBaidu()
        response = self.service.handle(
            {"action": "translate_selection", "text": "Liverpool are playing well."}
        )
        self.assertEqual("lookup_failed", response["status"])
        self.assertIn("未配置有道翻译后备", response["message"])

    def test_translate_selection_reports_both_provider_failures_safely(self):
        class FailingBaidu:
            def translate(self, _text):
                raise BaiduTranslateError("百度翻译错误 54003")

        class FailingYoudao:
            def translate(self, _text):
                raise YoudaoTranslateError("有道文本翻译错误 110")

        self.service.translator_factory = lambda _id, _key: FailingBaidu()
        self.service.youdao_factory = lambda _id, _key: FailingYoudao()
        response = self.service.handle(
            {"action": "translate_selection", "text": "Liverpool are playing well."}
        )
        self.assertEqual("lookup_failed", response["status"])
        self.assertIn("百度和有道翻译均失败", response["message"])
        self.assertNotIn("secret", repr(response))

    def test_youdao_translation_test_returns_preview_without_writing(self):
        before = self.chapter.read_bytes()
        response = self.service.handle(
            {"action": "test_youdao_translation", "text": "Liverpool are playing well."}
        )
        self.assertTrue(response["ok"])
        self.assertEqual("Liverpool are playing well.", response["preview"]["sourceText"])
        self.assertEqual("有道翻译结果", response["preview"]["translatedText"])
        self.assertEqual("youdao", response["preview"]["source"])
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
        self.assertEqual(str(self.news.resolve()), response["path"])
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
