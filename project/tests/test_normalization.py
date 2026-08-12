import unittest

from src.normalization import normalize


class TestNormalization(unittest.TestCase):
    def test_punctuation_preserves_word_boundaries(self):
        self.assertEqual(normalize("be,that"), "be that")
        self.assertEqual(normalize("be, that"), "be that")
        self.assertEqual(normalize("be that"), "be that")

    def test_normalizes_case_and_whitespace(self):
        self.assertEqual(normalize("  HELLO!!!\tWORLD  "), "hello world")


if __name__ == "__main__":
    unittest.main()
