import tempfile
import unittest
from pathlib import Path

from src.models import SentenceData
from src.protobuf_store import load_corpus_chunks, save_corpus_chunks


class ProtobufStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sentences = [
            SentenceData(7, "Hello, world!", "hello world", "a.txt", 2),
            SentenceData(8, "Second line", "second line", "a.txt", 3),
            SentenceData(9, "Nested text", "nested text", "b/c.txt", 11),
        ]

    def test_round_trip_preserves_every_field_across_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = save_corpus_chunks(self.sentences, directory, chunk_size=2)
            loaded = list(load_corpus_chunks(directory))

        self.assertEqual([path.name for path in paths], [
            "corpus-00000.pb",
            "corpus-00001.pb",
        ])
        self.assertEqual(loaded, self.sentences)

    def test_refuses_to_overwrite_an_existing_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            save_corpus_chunks(self.sentences, directory)

            with self.assertRaises(FileExistsError):
                save_corpus_chunks(self.sentences, directory)

    def test_chunk_size_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_corpus_chunks(self.sentences, directory, chunk_size=0)

    def test_missing_input_directory_is_rejected(self) -> None:
        missing = Path(tempfile.gettempdir()) / "missing-protobuf-corpus-dir"
        with self.assertRaises(NotADirectoryError):
            list(load_corpus_chunks(missing))


if __name__ == "__main__":
    unittest.main()
