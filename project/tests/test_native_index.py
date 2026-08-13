import unittest
import tempfile
from pathlib import Path

from src.autocomplete import select_indexed_completions, select_native_completions
from src.indexer import build_search_data
from src.models import SentenceData
from src.native_index import (
    DEFAULT_LIBRARY_PATH,
    NativeIndex,
    protobuf_corpus_fingerprint,
)
from src.protobuf_store import save_corpus_chunks


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
            self.native_index,
        )

        self.assertEqual(native_results, python_results)

    def test_one_typo_matches_python_results(self) -> None:
        python_results = select_indexed_completions("thf cat", self.search_data)
        native_results = select_native_completions(
            "thf cat",
            self.native_index,
        )

        self.assertEqual(native_results, python_results)

    def test_closed_engine_cannot_be_used(self) -> None:
        self.native_index.close()

        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.native_index.find_exact_top_k("the")

    def test_cpp_loads_protobuf_chunks_without_python_index(self) -> None:
        sentences = list(self.search_data.sentences_by_id.values())
        with tempfile.TemporaryDirectory() as directory:
            save_corpus_chunks(sentences, directory, chunk_size=2)
            loaded = NativeIndex.from_protobuf_directory(directory)
            try:
                self.assertEqual(len(loaded), len(sentences))
                results = select_native_completions("the", loaded)
            finally:
                loaded.close()

        expected = select_indexed_completions("the", self.search_data)
        self.assertEqual(results, expected)

    def test_second_protobuf_load_reuses_the_native_cache(self) -> None:
        sentences = list(self.search_data.sentences_by_id.values())
        with tempfile.TemporaryDirectory() as directory:
            save_corpus_chunks(sentences, directory, chunk_size=2)
            first = NativeIndex.from_protobuf_directory(directory)
            first.close()

            cache_path = Path(directory) / ".autocomplete-native-index.cache"
            self.assertTrue(cache_path.is_file())

            second = NativeIndex.from_protobuf_directory(directory)
            try:
                self.assertEqual(len(second), len(sentences))
                self.assertEqual(
                    select_native_completions("the", second),
                    select_indexed_completions("the", self.search_data),
                )
            finally:
                second.close()


class ProtobufCorpusFingerprintTests(unittest.TestCase):
    def test_changes_when_chunk_metadata_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            chunk = Path(directory) / "corpus-00000.pb"
            chunk.write_bytes(b"first")
            first = protobuf_corpus_fingerprint(directory)

            chunk.write_bytes(b"second value")
            second = protobuf_corpus_fingerprint(directory)

        self.assertNotEqual(first, second)

    def test_rejects_directory_without_corpus_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                protobuf_corpus_fingerprint(directory)


if __name__ == "__main__":
    unittest.main()
