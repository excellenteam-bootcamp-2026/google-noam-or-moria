import unittest
from src.normalization import normalize

class TestNormalization(unittest.TestCase):
    def test_lowercase_conversion(self):
        # Ensure text is converted to lowercase
        self.assertEqual(normalize("HELLO WORLD"), "hello world")
        
    def test_punctuation_removal(self):
        # Ensure all punctuation is removed
        self.assertEqual(normalize("hello, world! it's python."), "hello world its python")
        
    def test_whitespace_reduction(self):
        # Ensure multiple spaces are reduced to a single space
        self.assertEqual(normalize("hello    world \t test"), "hello world test")
        
    def test_strip_edges(self):
        # Ensure leading and trailing whitespace is removed
        self.assertEqual(normalize("  hello world  "), "hello world")

    def test_empty_string(self):
        # Ensure empty strings are handled correctly
        self.assertEqual(normalize(""), "")

if __name__ == '__main__':
    unittest.main()