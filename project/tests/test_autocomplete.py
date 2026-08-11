from unittest.mock import patch

from src.autocomplete import (
    build_best_completions,
    get_best_k_completions,
    select_best_completions,
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
