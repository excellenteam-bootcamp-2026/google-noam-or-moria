import unittest

# Import from the src module directly
from src.matcher import calculate_best_match

class TestMatcher(unittest.TestCase):
    def setUp(self):
        # The base sentence from the project appendix
        self.sentence = "To be or not to be, that is the question."

    def test_exact_matches(self):
        # All 5 letters match
        self.assertEqual(calculate_best_match("To be", self.sentence), 10)
        # All 6 letters match
        self.assertEqual(calculate_best_match("or Not", self.sentence), 12)
        # All 7 letters match ignoring comma
        self.assertEqual(calculate_best_match("be, that", self.sentence), 14)

    def test_substitution_errors(self):
        # Base 10 minus 5 for incorrect first letter
        self.assertEqual(calculate_best_match("2o be", self.sentence), 5)
        # Base 10 minus 2 for incorrect fourth letter
        self.assertEqual(calculate_best_match("to pe", self.sentence), 8)
        # Error at the end of the input string
        self.assertEqual(calculate_best_match("To bx", self.sentence), 9)

    def test_insertion_errors(self):
        # Base 12 minus 4 for added fourth letter k
        self.assertEqual(calculate_best_match("or knot", self.sentence), 8)

    def test_deletion_errors(self):
        # Missing character in the query
        self.assertEqual(calculate_best_match("To b", self.sentence), 8)
        
    def test_multiple_errors_return_none(self):
        # Needs more than one letter correction, so it cannot be a match
        self.assertIsNone(calculate_best_match("not be", self.sentence))

    def test_empty_input(self):
        # Empty input should return None
        self.assertIsNone(calculate_best_match("", self.sentence))

    def test_double_spaces_and_punctuation(self):
        # Should normalize to "to be" and match perfectly with score 10
        self.assertEqual(calculate_best_match("To   be!!", self.sentence), 10)

if __name__ == '__main__':
    unittest.main()