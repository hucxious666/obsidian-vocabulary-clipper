import unittest

from clipper.selection import InvalidSelection, normalize_selection, normalize_translation_selection


class NormalizeSelectionTests(unittest.TestCase):
    def test_strips_edge_punctuation_and_collapses_whitespace(self):
        self.assertEqual("old school", normalize_selection("  (old   school),  "))

    def test_accepts_hyphens_and_apostrophes(self):
        self.assertEqual("once-in-a-lifetime", normalize_selection("once-in-a-lifetime"))
        self.assertEqual("don't", normalize_selection("don't"))

    def test_rejects_more_than_five_words(self):
        with self.assertRaises(InvalidSelection):
            normalize_selection("one two three four five six")

    def test_rejects_non_english_selection(self):
        with self.assertRaises(InvalidSelection):
            normalize_selection("hello 世界")

    def test_normalizes_sentence_for_translation(self):
        self.assertEqual(
            "Liverpool are playing well.",
            normalize_translation_selection("  Liverpool\nare   playing well.  "),
        )

    def test_translation_accepts_numbers_and_punctuation(self):
        self.assertEqual(
            "Liverpool won 2 games!",
            normalize_translation_selection("Liverpool won 2 games!"),
        )

    def test_translation_rejects_single_word_mixed_language_and_long_text(self):
        for value in ("player", "hello world 世界", "hello world привет", "one " * 126):
            with self.subTest(value=value[:20]):
                with self.assertRaisesRegex(InvalidSelection, "英文句子"):
                    normalize_translation_selection(value)


if __name__ == "__main__":
    unittest.main()
