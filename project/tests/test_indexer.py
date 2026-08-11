from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.indexer import (
    build_search_data,
    create_ngrams,
    find_candidate_ids,
    initialize,
)
from src.models import SentenceData


def make_sentence(sentence_id: int, text: str) -> SentenceData:
    return SentenceData(
        sentence_id=sentence_id,
        original_sentence=text,
        normalized_sentence=text,
        source_path=f"file-{sentence_id}.txt",
        offset=sentence_id + 1,
    )


class CreateNGramsTests(TestCase):
    def test_creates_unique_contiguous_ngrams(self) -> None:
        self.assertEqual(create_ngrams("banana", 2), {"ba", "an", "na"})

    def test_text_shorter_than_n_has_no_ngrams(self) -> None:
        self.assertEqual(create_ngrams("ab", 3), set())

    def test_non_positive_n_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_ngrams("text", 0)


class BuildSearchDataTests(TestCase):
    def test_builds_all_indexes_and_sentence_lookup(self) -> None:
        first = make_sentence(4, "python programming")
        second = make_sentence(9, "python testing")

        search_data = build_search_data([first, second])

        self.assertIs(search_data.sentences_by_id[4], first)
        self.assertIs(search_data.sentences_by_id[9], second)
        self.assertEqual(search_data.unigram_index["p"], {4, 9})
        self.assertEqual(search_data.bigram_index["py"], {4, 9})
        self.assertEqual(search_data.trigram_index["pro"], {4})

    def test_repeated_ngram_adds_sentence_only_once(self) -> None:
        search_data = build_search_data([make_sentence(3, "banana")])

        self.assertEqual(search_data.bigram_index["an"], {3})

    def test_duplicate_sentence_ids_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_search_data(
                [make_sentence(2, "first"), make_sentence(2, "second")]
            )

    def test_initialize_loads_nested_files_and_builds_indexes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "nested"
            nested.mkdir()
            (nested / "sentences.txt").write_text(
                "Python, Programming!\n", encoding="utf-8"
            )

            search_data = initialize(str(root))

            sentence = search_data.sentences_by_id[0]
            self.assertEqual(sentence.original_sentence, "Python, Programming!")
            self.assertEqual(sentence.normalized_sentence, "python programming")
            self.assertEqual(search_data.trigram_index["pro"], {0})


class FindCandidateIdsTests(TestCase):
    def setUp(self) -> None:
        self.search_data = build_search_data(
            [
                make_sentence(0, "python programming"),
                make_sentence(1, "testing tools"),
                make_sentence(2, "program management"),
            ]
        )

    def test_empty_query_has_no_candidates(self) -> None:
        self.assertEqual(find_candidate_ids("", self.search_data), set())

    def test_one_character_query_returns_every_sentence(self) -> None:
        self.assertEqual(find_candidate_ids("x", self.search_data), {0, 1, 2})

    def test_short_query_uses_unigrams(self) -> None:
        self.assertEqual(find_candidate_ids("py", self.search_data), {0, 2})

    def test_medium_query_uses_bigrams(self) -> None:
        self.assertEqual(find_candidate_ids("prog", self.search_data), {0, 2})

    def test_long_query_uses_trigrams(self) -> None:
        self.assertEqual(find_candidate_ids("program", self.search_data), {0, 2})

    def test_typo_still_returns_the_expected_candidate(self) -> None:
        candidates = find_candidate_ids("progranming", self.search_data)

        self.assertIn(0, candidates)
