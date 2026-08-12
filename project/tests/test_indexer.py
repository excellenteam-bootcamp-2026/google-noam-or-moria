from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from src.indexer import (
    build_search_data,
    create_ngrams,
    find_candidate_ids,
    find_exact_candidate_ids,
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

    def test_repeated_characters_create_one_unique_ngram(self) -> None:
        self.assertEqual(create_ngrams("aaaaaaaa", 3), {"aaa"})

    def test_repeated_phrase_keeps_unique_ngrams(self) -> None:
        grams = create_ngrams("banana banana", 3)

        self.assertEqual(
            grams,
            {"ban", "ana", "nan", "na ", "a b", " ba"},
        )


class BuildSearchDataTests(TestCase):
    def test_builds_all_indexes_and_sentence_lookup(self) -> None:
        first = make_sentence(4, "python programming")
        second = make_sentence(9, "python testing")

        search_data = build_search_data([first, second])

        self.assertIs(search_data.sentences_by_id[4], first)
        self.assertIs(search_data.sentences_by_id[9], second)
        self.assertEqual(search_data.unigram_index["p"], [4, 9])
        self.assertEqual(search_data.bigram_index["py"], [4, 9])
        self.assertEqual(search_data.trigram_index["pro"], [4])

    def test_indexes_use_lists(self) -> None:
        search_data = build_search_data([make_sentence(1, "python")])

        self.assertIsInstance(search_data.unigram_index["p"], list)
        self.assertIsInstance(search_data.bigram_index["py"], list)
        self.assertIsInstance(search_data.trigram_index["pyt"], list)

    def test_repeated_ngram_adds_sentence_only_once(self) -> None:
        search_data = build_search_data([make_sentence(3, "banana")])

        self.assertEqual(search_data.bigram_index["an"], [3])

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
            self.assertEqual(search_data.trigram_index["pro"], [0])

    def test_initialize_uses_configured_corpus_when_path_is_omitted(self) -> None:
        configured_path = "configured-corpus"

        with (
            patch.dict(
                "os.environ",
                {"GOOGLE_AUTOCOMPLETE_CORPUS": configured_path},
            ),
            patch("src.indexer.load_sentences", return_value=[]) as loader,
        ):
            search_data = initialize()

        loader.assert_called_once_with(configured_path)
        self.assertEqual(search_data.sentences_by_id, {})

    def test_explicit_path_overrides_configured_corpus(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"GOOGLE_AUTOCOMPLETE_CORPUS": "configured-corpus"},
            ),
            patch("src.indexer.load_sentences", return_value=[]) as loader,
        ):
            initialize("explicit-corpus")

        loader.assert_called_once_with("explicit-corpus")


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

    def test_one_character_query_returns_only_sentences_containing_it(self) -> None:
        self.assertEqual(find_candidate_ids("p", self.search_data), {0, 2})

    def test_unknown_one_character_query_has_no_candidates(self) -> None:
        self.assertEqual(find_candidate_ids("x", self.search_data), set())

    def test_short_query_uses_unigrams(self) -> None:
        self.assertEqual(find_candidate_ids("py", self.search_data), {0, 2})

    def test_medium_query_uses_bigrams(self) -> None:
        self.assertEqual(find_candidate_ids("prog", self.search_data), {0, 2})

    def test_long_query_uses_trigrams(self) -> None:
        self.assertEqual(find_candidate_ids("program", self.search_data), {0, 2})

    def test_typo_still_returns_the_expected_candidate(self) -> None:
        candidates = find_candidate_ids("progranming", self.search_data)

        self.assertIn(0, candidates)

    def test_three_character_query_rejects_only_one_shared_character(self) -> None:
        search_data = build_search_data(
            [make_sentence(0, "a"), make_sentence(1, "car")]
        )

        self.assertEqual(find_candidate_ids("cat", search_data), {1})

    def test_long_query_requires_most_trigrams(self) -> None:
        search_data = build_search_data(
            [
                make_sentence(0, "programming language"),
                make_sentence(1, "progress report"),
            ]
        )

        self.assertEqual(find_candidate_ids("programming", search_data), {0})

    def test_one_typo_in_long_query_keeps_correct_sentence(self) -> None:
        search_data = build_search_data(
            [make_sentence(0, "programming language")]
        )

        self.assertEqual(find_candidate_ids("progranming", search_data), {0})

    def test_repeated_character_query_does_not_duplicate_candidate_count(self) -> None:
        search_data = build_search_data(
            [
                make_sentence(0, "aaaaaaaa"),
                make_sentence(1, "contains aaa once"),
                make_sentence(2, "unrelated sentence"),
            ]
        )

        self.assertEqual(find_candidate_ids("aaaaaaaa", search_data), {0, 1})

    def test_repeated_phrase_query_keeps_matching_sentence(self) -> None:
        search_data = build_search_data(
            [
                make_sentence(0, "banana banana smoothie"),
                make_sentence(1, "banana bread"),
                make_sentence(2, "unrelated sentence"),
            ]
        )

        candidates = find_candidate_ids("banana banana", search_data)

        self.assertIn(0, candidates)
        self.assertNotIn(2, candidates)


class FindExactCandidateIdsTests(TestCase):
    def setUp(self) -> None:
        self.search_data = build_search_data(
            [
                make_sentence(0, "cat catalog"),
                make_sentence(1, "a dog"),
                make_sentence(2, "educate"),
                make_sentence(3, "concatenate strings"),
                make_sentence(4, "scattered letters"),
            ]
        )

    def test_empty_query_has_no_exact_candidates(self) -> None:
        self.assertEqual(find_exact_candidate_ids("", self.search_data), set())

    def test_one_character_uses_unigram_index(self) -> None:
        self.assertEqual(
            find_exact_candidate_ids("c", self.search_data),
            {0, 2, 3, 4},
        )

    def test_two_characters_use_bigram_index(self) -> None:
        self.assertEqual(
            find_exact_candidate_ids("ca", self.search_data),
            {0, 2, 3, 4},
        )

    def test_long_query_uses_its_rarest_trigram_posting(self) -> None:
        self.assertEqual(
            find_exact_candidate_ids("concatenate", self.search_data),
            {3},
        )

    def test_rarest_posting_is_returned_without_intersecting_all_postings(self) -> None:
        search_data = build_search_data(
            [
                make_sentence(0, "abcdef"),
                make_sentence(1, "contains cde only"),
                make_sentence(2, "abc bcd def"),
                make_sentence(3, "another abc bcd def"),
            ]
        )

        # "cde" has the shortest posting list. Candidate 1 is intentionally
        # a false positive that the matcher must reject.
        self.assertEqual(
            find_exact_candidate_ids("abcdef", search_data),
            {0, 1},
        )

    def test_missing_trigram_makes_exact_candidate_set_empty(self) -> None:
        self.assertEqual(
            find_exact_candidate_ids("catxyz", self.search_data),
            set(),
        )

    def test_long_query_does_not_scan_unrelated_sentences(self) -> None:
        self.assertEqual(
            find_exact_candidate_ids("catalog", self.search_data),
            {0},
        )

    def test_repeated_character_exact_query_returns_strong_candidates(self) -> None:
        search_data = build_search_data(
            [
                make_sentence(0, "aaaaaaaa"),
                make_sentence(1, "contains aaa once"),
                make_sentence(2, "unrelated sentence"),
            ]
        )

        # The index only produces candidates. The matcher must still verify
        # repetitions, order, and an actual exact substring match.
        self.assertEqual(
            find_exact_candidate_ids("aaaaaaaa", search_data),
            {0, 1},
        )

    def test_repeated_phrase_exact_query_keeps_correct_candidate(self) -> None:
        search_data = build_search_data(
            [
                make_sentence(0, "banana banana smoothie"),
                make_sentence(1, "banana bread"),
            ]
        )

        self.assertEqual(
            find_exact_candidate_ids("banana banana", search_data),
            {0},
        )
