import unittest
import sys
import os

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from matcher import calculate_best_match

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

    def test_insertion_errors(self):
        # Base 12 minus 4 for added fourth letter k
        self.assertEqual(calculate_best_match("or knot", self.sentence), 8)

    def test_multiple_errors_return_none(self):
        # Needs more than one letter correction, so it cannot be a match
        self.assertIsNone(calculate_best_match("not be", self.sentence))

if __name__ == '__main__':
    unittest.main()