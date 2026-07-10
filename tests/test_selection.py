import unittest

from clipper.selection import InvalidSelection, normalize_selection


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


if __name__ == "__main__":
    unittest.main()
