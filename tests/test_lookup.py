import sqlite3
import tempfile
import unittest
from pathlib import Path

from clipper.dictionary import DictionaryLookup, LookupNotFound
from clipper.dictionary_schema import create_pack_schema, write_pack_metadata
from clipper.translator import BaiduTranslateError, BaiduTranslator
from clipper.youdao import YoudaoTranslateError, YoudaoTranslator


class DictionaryLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "dict.db"
        connection = sqlite3.connect(self.db_path)
        create_pack_schema(connection)
        write_pack_metadata(connection, {
            "id": "fixture", "name": "Fixture Dictionary",
            "source_language": "en", "target_language": "zh-Hans",
        })
        connection.executemany(
            "INSERT INTO entries(word, phonetic, definition, translation, pos, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("run", "rʌn", "move swiftly", "v. 跑", "verb", '{"tag":"cet4"}'),
                ("old school", "əʊld skuːl", "traditional", "守旧派", "noun", "{}"),
                ("circumvent", "ˌsɜːkəmˈvent", "avoid", "vt. 绕行, 陷害, 包围, 智取", "verb", "{}"),
                ("circumvents", "ˌsɜːkəmˈvents", "surrounds", "n. 环绕\nvt. 规避", "verb", "{}"),
            ],
        )
        run_id = connection.execute("SELECT id FROM entries WHERE word='run'").fetchone()[0]
        sense_id = connection.execute(
            "INSERT INTO senses(entry_id, position, part_of_speech, gloss, translated_gloss, tags) "
            "VALUES (?, 0, 'verb', 'move swiftly', '跑', 'intransitive')", (run_id,)
        ).lastrowid
        connection.execute(
            "INSERT INTO examples(sense_id, position, text) VALUES (?, 0, 'She runs daily.')",
            (sense_id,),
        )
        connection.executemany(
            "INSERT INTO forms(form, lemma) VALUES (?, ?)",
            [("running", "run"), ("circumvents", "circumvent")],
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_phrase_lookup(self):
        result = DictionaryLookup(self.db_path).lookup("old school")
        self.assertEqual("əʊld skuːl", result.phonetic)

    def test_single_word_falls_back_to_lemma(self):
        result = DictionaryLookup(self.db_path).lookup("running")
        self.assertEqual("run", result.matched_word)

    def test_returns_pack_source_structured_senses_examples_and_metadata(self):
        result = DictionaryLookup(self.db_path).lookup("run")
        self.assertEqual("fixture", result.source_id)
        self.assertEqual("Fixture Dictionary", result.source_name)
        self.assertEqual("move swiftly", result.definition)
        self.assertEqual("verb", result.senses[0].part_of_speech)
        self.assertEqual("跑", result.senses[0].translated_gloss)
        self.assertEqual("She runs daily.", result.examples[0].text)
        self.assertEqual("cet4", result.metadata["tag"])

    def test_inflected_word_keeps_exact_phonetic_and_uses_lemma_translation(self):
        result = DictionaryLookup(self.db_path).lookup("circumvents")
        self.assertEqual("ˌsɜːkəmˈvents", result.phonetic)
        self.assertEqual("vt. 绕行, 陷害, 包围, 智取", result.translation)

    def test_missing_phonetic_is_not_accepted(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "INSERT INTO entries(word, phonetic, translation) VALUES ('silent', '', '无声')"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(LookupNotFound):
            DictionaryLookup(self.db_path).lookup("silent")


class BaiduTranslatorTests(unittest.TestCase):
    def test_builds_official_signature_and_returns_translation(self):
        requests = []

        def fake_request(url, payload, timeout):
            requests.append((url, payload, timeout))
            return {"trans_result": [{"src": "word", "dst": "单词"}]}

        translator = BaiduTranslator("appid", "secret", requester=fake_request, salt_factory=lambda: "123")
        self.assertEqual("单词", translator.translate("word"))
        self.assertEqual("en", requests[0][1]["from"])
        self.assertEqual("zh", requests[0][1]["to"])
        self.assertEqual(32, len(requests[0][1]["sign"]))
        self.assertNotIn("secret", repr(requests))

    def test_api_error_is_sanitized(self):
        def fake_request(url, payload, timeout):
            return {"error_code": "54001", "error_msg": "Invalid Sign"}

        translator = BaiduTranslator("appid", "secret", requester=fake_request)
        with self.assertRaisesRegex(BaiduTranslateError, "54001") as error:
            translator.translate("word")
        self.assertNotIn("secret", str(error.exception))


class YoudaoTranslatorTests(unittest.TestCase):
    def test_builds_v3_signature_and_parses_translation_result(self):
        requests = []

        def fake_request(url, payload, timeout):
            requests.append((url, payload, timeout))
            return {
                "errorCode": "0",
                "query": "Liverpool are playing well.",
                "translation": ["利物浦踢得很好。"],
            }

        client = YoudaoTranslator(
            "app-key",
            "app-secret",
            requester=fake_request,
            salt_factory=lambda: "123",
            time_factory=lambda: 1_700_000_000,
        )
        result = client.translate("Liverpool are playing well.")

        self.assertEqual("利物浦踢得很好。", result)
        self.assertEqual("https://openapi.youdao.com/api", requests[0][0])
        payload = requests[0][1]
        self.assertEqual("v3", payload["signType"])
        self.assertEqual("en", payload["from"])
        self.assertEqual("zh-CHS", payload["to"])
        self.assertEqual(64, len(payload["sign"]))
        self.assertNotIn("app-secret", repr(requests))

    def test_joins_multiple_translation_results(self):
        def fake_request(_url, _payload, _timeout):
            return {"errorCode": "0", "translation": ["第一句。", "第二句。"]}

        result = YoudaoTranslator(
            "app-key", "app-secret", requester=fake_request
        ).translate("First sentence. Second sentence.")
        self.assertEqual("第一句。；第二句。", result)

    def test_service_permission_error_is_actionable_and_sanitized(self):
        def fake_request(_url, _payload, _timeout):
            return {"errorCode": "110"}

        client = YoudaoTranslator("app-key", "app-secret", requester=fake_request)
        with self.assertRaisesRegex(YoudaoTranslateError, "有道文本翻译错误 110") as error:
            client.translate("Liverpool are playing well.")
        self.assertNotIn("app-secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()
