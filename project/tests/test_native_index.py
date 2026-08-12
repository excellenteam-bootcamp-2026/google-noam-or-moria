import unittest

from src.autocomplete import select_indexed_completions, select_native_completions
from src.indexer import build_search_data
from src.models import SentenceData
from src.native_index import DEFAULT_LIBRARY_PATH, NativeIndex


@unittest.skipUnless(
    DEFAULT_LIBRARY_PATH.is_file(),
    "Native library has not been compiled",
)
class NativeIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        sentences = [
            SentenceData(1, "The dog runs", "the dog runs", "z.txt", 2),
            SentenceData(2, "The cat sleeps", "the cat sleeps", "a.txt", 3),
            SentenceData(3, "A bird flies", "a bird flies", "b.txt", 4),
            SentenceData(4, "The cow rests", "the cow rests", "c.txt", 5),
            SentenceData(5, "The ant walks", "the ant walks", "d.txt", 6),
            SentenceData(6, "The fox jumps", "the fox jumps", "e.txt", 7),
        ]
        self.search_data = build_search_data(sentences)
        self.native_index = NativeIndex.from_search_data(self.search_data)

    def tearDown(self) -> None:
        self.native_index.close()

    def test_exact_top_k_matches_python_order(self) -> None:
        python_results = select_indexed_completions("the", self.search_data)
        native_results = select_native_completions(
            "the",
            self.search_data,
            self.native_index,
        )

        self.assertEqual(native_results, python_results)

    def test_one_typo_matches_python_results(self) -> None:
        python_results = select_indexed_completions("thf cat", self.search_data)
        native_results = select_native_completions(
            "thf cat",
            self.search_data,
            self.native_index,
        )

        self.assertEqual(native_results, python_results)

    def test_closed_engine_cannot_be_used(self) -> None:
        self.native_index.close()

        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.native_index.find_exact_top_k("the")


if __name__ == "__main__":
    unittest.main()
