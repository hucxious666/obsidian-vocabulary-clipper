import unittest

from clipper.meaning import normalize_ecdict_translation


class MeaningNormalizationTests(unittest.TestCase):
    def test_normalizes_part_of_speech_and_separators(self):
        source = "a. 可耻的, 不名誉的, 下流的"
        self.assertEqual("adj.可耻的；不名誉的；下流的", normalize_ecdict_translation(source))

    def test_preserves_multiple_domains_and_removes_duplicate_meanings(self):
        source = "n. 增殖, 激增\n[医] 增生, 增殖"
        self.assertEqual("n.增殖；激增；[医]增生", normalize_ecdict_translation(source))

    def test_converts_ecdict_literal_newline_escape(self):
        source = r"n. 增殖, 激增\n[医] 增生, 增殖"
        self.assertEqual("n.增殖；激增；[医]增生", normalize_ecdict_translation(source))

    def test_keeps_distinct_parts_of_speech(self):
        source = "n. 包围, 绕行\nvt. 绕行, 陷害, 包围, 智取"
        self.assertEqual("n.包围；绕行；vt.绕行；陷害；包围；智取", normalize_ecdict_translation(source))


if __name__ == "__main__":
    unittest.main()
