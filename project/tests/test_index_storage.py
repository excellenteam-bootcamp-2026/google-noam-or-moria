from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.index_storage import (
    InvalidSearchIndexError,
    file_hash,
    load_search_data,
    save_search_data,
)
from src.indexer import build_search_data
from src.models import SentenceData


def make_sentence(sentence_id: int, text: str) -> SentenceData:
    return SentenceData(
        sentence_id=sentence_id,
        original_sentence=text,
        normalized_sentence=text.lower(),
        source_path="source.txt",
        offset=sentence_id + 1,
    )


class IndexStorageTests(TestCase):
    def test_round_trip_preserves_sentences_indexes_and_hash(self) -> None:
        search_data = build_search_data(
            [make_sentence(0, "Cat"), make_sentence(1, "Catalog")]
        )

        with TemporaryDirectory() as temporary_directory:
            index_path = Path(temporary_directory) / "search-index.pb"
            save_search_data(search_data, "archive-hash", index_path)
            restored, saved_hash = load_search_data(index_path)

        self.assertEqual(restored, search_data)
        self.assertEqual(saved_hash, "archive-hash")

    def test_loaded_posting_lists_remain_lists(self) -> None:
        search_data = build_search_data([make_sentence(0, "Cat")])

        with TemporaryDirectory() as temporary_directory:
            index_path = Path(temporary_directory) / "search-index.pb"
            save_search_data(search_data, "hash", index_path)
            restored, _ = load_search_data(index_path)

        self.assertIsInstance(restored.unigram_index["c"], list)
        self.assertIsInstance(restored.bigram_index["ca"], list)
        self.assertIsInstance(restored.trigram_index["cat"], list)

    def test_file_hash_changes_when_archive_changes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "Archive.zip"
            archive_path.write_bytes(b"first")
            first_hash = file_hash(archive_path)
            archive_path.write_bytes(b"second")

            self.assertNotEqual(first_hash, file_hash(archive_path))

    def test_corrupt_index_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            index_path = Path(temporary_directory) / "search-index.pb"
            index_path.write_bytes(b"this is not protobuf")

            with self.assertRaises(InvalidSearchIndexError):
                load_search_data(index_path)

    def test_save_replaces_existing_index(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            index_path = Path(temporary_directory) / "search-index.pb"
            first = build_search_data([make_sentence(0, "first")])
            second = build_search_data([make_sentence(1, "second")])
            save_search_data(first, "old", index_path)
            save_search_data(second, "new", index_path)

            restored, saved_hash = load_search_data(index_path)

        self.assertEqual(restored, second)
        self.assertEqual(saved_hash, "new")
