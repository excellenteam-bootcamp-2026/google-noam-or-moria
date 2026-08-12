from unittest.mock import Mock, patch

from src.autocomplete import (
    build_best_completions,
    get_best_k_completions,
    select_best_completions,
    select_staged_completions,
    set_sentences,
)
from src.models import SearchData, SentenceData


def sentence(text: str, path: str = "data.txt", offset: int = 1) -> SentenceData:
    return SentenceData(0, text, text.lower(), path, offset)


def test_returns_only_matching_sentences_with_metadata() -> None:
    sentences = [
        sentence("First result", "first.txt", 3),
        sentence("Ignored result", "ignored.txt", 7),
    ]

    with patch(
        "src.autocomplete.calculate_best_match", side_effect=[12, None]
    ):
        results = select_best_completions("result", sentences)

    assert len(results) == 1
    assert results[0].completed_sentence == "First result"
    assert results[0].source_text == "first.txt"
    assert results[0].offset == 3
    assert results[0].score == 12


def test_sorts_by_score_then_alphabetically_and_limits_to_five() -> None:
    sentences = [
        sentence(name)
        for name in ["Zulu", "Echo", "Alpha", "Golf", "Beta", "Delta"]
    ]

    with patch(
        "src.autocomplete.calculate_best_match",
        side_effect=[10, 12, 12, 9, 12, 11],
    ):
        results = select_best_completions("query", sentences)

    assert [result.completed_sentence for result in results] == [
        "Alpha",
        "Beta",
        "Echo",
        "Delta",
        "Zulu",
    ]


def test_public_function_uses_initialized_sentences() -> None:
    set_sentences([sentence("Stored sentence")])

    with patch("src.autocomplete.calculate_best_match", return_value=8):
        results = get_best_k_completions("stored")

    assert [result.completed_sentence for result in results] == ["Stored sentence"]


def test_empty_query_and_non_positive_limit_return_no_results() -> None:
    with patch("src.autocomplete.calculate_best_match") as matcher:
        assert select_best_completions("", [sentence("Anything")]) == []
        assert select_best_completions("query", [sentence("Anything")], k=0) == []

    matcher.assert_not_called()


def test_builds_ranked_results_from_indexed_candidate_scores() -> None:
    indexed_sentences = {
        10: SentenceData(10, "Zulu result", "zulu result", "z.txt", 2),
        20: SentenceData(20, "Alpha result", "alpha result", "a.txt", 4),
        30: SentenceData(30, "Ignored result", "ignored result", "i.txt", 8),
    }
    search_data = SearchData(indexed_sentences, {}, {}, {})

    results = build_best_completions(
        candidate_scores={10: 12, 20: 12, 30: None},
        search_data=search_data,
    )

    assert [result.completed_sentence for result in results] == [
        "Alpha result",
        "Zulu result",
    ]
    assert results[0].source_text == "a.txt"
    assert results[0].offset == 4
    assert results[0].score == 12


def test_indexed_results_are_limited_to_requested_size() -> None:
    indexed_sentences = {
        sentence_id: SentenceData(
            sentence_id,
            f"Sentence {sentence_id}",
            f"sentence {sentence_id}",
            "data.txt",
            sentence_id,
        )
        for sentence_id in range(1, 8)
    }
    search_data = SearchData(indexed_sentences, {}, {}, {})
    scores = {sentence_id: sentence_id for sentence_id in indexed_sentences}

    results = build_best_completions(scores, search_data, k=5)

    assert [result.score for result in results] == [7, 6, 5, 4, 3]


def test_returns_fewer_than_five_when_only_two_matches_exist() -> None:
    indexed_sentences = {
        1: SentenceData(1, "First", "first", "a.txt", 1),
        2: SentenceData(2, "Second", "second", "b.txt", 2),
    }
    search_data = SearchData(indexed_sentences, {}, {}, {})

    results = build_best_completions({1: 8, 2: 6}, search_data)

    assert len(results) == 2


def test_none_scores_are_not_returned() -> None:
    indexed_sentences = {
        1: SentenceData(1, "No match", "no match", "a.txt", 1),
    }
    search_data = SearchData(indexed_sentences, {}, {}, {})

    assert build_best_completions({1: None}, search_data) == []


def test_non_positive_indexed_limit_returns_no_results() -> None:
    search_data = SearchData({}, {}, {}, {})

    assert build_best_completions({}, search_data, k=0) == []


def indexed_search_data(count: int = 7) -> SearchData:
    sentences = {
        sentence_id: SentenceData(
            sentence_id,
            f"Sentence {sentence_id}",
            f"sentence {sentence_id}",
            "data.txt",
            sentence_id,
        )
        for sentence_id in range(1, count + 1)
    }
    return SearchData(sentences, {}, {}, {})


def test_staged_search_stops_after_five_exact_matches() -> None:
    search_data = indexed_search_data()
    exact_finder = lambda query, data: {1, 2, 3, 4, 5}
    fuzzy_finder = Mock()

    with patch("src.autocomplete.calculate_best_match") as matcher:
        results = select_staged_completions(
            "sentence",
            search_data,
            exact_finder,
            fuzzy_finder,
        )

    assert len(results) == 5
    matcher.assert_not_called()
    fuzzy_finder.assert_not_called()


def test_staged_search_expands_when_fewer_than_five_exact_matches() -> None:
    search_data = indexed_search_data()
    exact_finder = lambda query, data: {1, 2}
    fuzzy_finder = lambda query, data: {1, 2, 3, 4}

    with patch(
        "src.autocomplete.calculate_best_match",
        side_effect=[8, 7],
    ) as matcher:
        results = select_staged_completions(
            "sentence",
            search_data,
            exact_finder,
            fuzzy_finder,
        )

    assert len(results) == 4
    assert matcher.call_count == 2


def test_staged_search_does_not_score_the_same_candidate_twice() -> None:
    search_data = indexed_search_data()

    with patch(
        "src.autocomplete.calculate_best_match",
        side_effect=[8, 7, 6],
    ) as matcher:
        select_staged_completions(
            "missing",
            search_data,
            lambda query, data: {1, 2},
            lambda query, data: {1, 2, 3},
        )

    assert matcher.call_count == 3
