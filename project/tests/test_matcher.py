import unittest

from src.matcher import calculate_best_match


class TestMatcher(unittest.TestCase):
    def setUp(self):
        self.sentence = "To be or not to be, that is the question."

    def test_exact_matches(self):
        self.assertEqual(calculate_best_match("To be", self.sentence), 10)
        self.assertEqual(calculate_best_match("or Not", self.sentence), 12)
        self.assertEqual(calculate_best_match("be, that", self.sentence), 14)

    def test_substitution_errors(self):
        self.assertEqual(calculate_best_match("2o be", self.sentence), 5)
        self.assertEqual(calculate_best_match("to pe", self.sentence), 8)
        self.assertEqual(calculate_best_match("To bx", self.sentence), 9)

    def test_added_character(self):
        self.assertEqual(calculate_best_match("or knot", self.sentence), 8)

    def test_missing_character(self):
        self.assertEqual(calculate_best_match("abdef", "abcdef"), 4)

    def test_repeated_characters_keep_the_best_edit_position(self):
        self.assertEqual(calculate_best_match("aab", "ab"), -4)

    def test_multiple_errors_return_none(self):
        self.assertIsNone(calculate_best_match("not be", self.sentence))

    def test_empty_input_returns_none(self):
        self.assertIsNone(calculate_best_match("", self.sentence))

    def test_normalizes_punctuation_and_whitespace(self):
        self.assertEqual(calculate_best_match("To   be!!", self.sentence), 10)
        self.assertEqual(calculate_best_match("be,that", self.sentence), 14)

    def test_long_query_with_one_error(self):
        query = "abcdefghijklmnopqrstuvwxyz" * 4
        sentence = f"prefix {query[:80]}x{query[81:]} suffix"
        self.assertEqual(calculate_best_match(query, sentence), len(query) * 2 - 1)


if __name__ == "__main__":
    unittest.main()
