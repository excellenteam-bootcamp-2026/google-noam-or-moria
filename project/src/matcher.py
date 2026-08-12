from __future__ import annotations

from src.normalization import normalize


def get_substitution_penalty(error_index: int) -> int:
    """Return the score penalty for one replaced character."""
    penalties = [5, 4, 3, 2]
    return penalties[error_index] if error_index < len(penalties) else 1


def get_missing_or_added_penalty(error_index: int) -> int:
    """Return the score penalty for one missing or added character."""
    penalties = [10, 8, 6, 4]
    return penalties[error_index] if error_index < len(penalties) else 2


def find_single_substitution_index(
    query: str,
    sentence: str,
    start: int,
) -> int | None:
    """Return the replacement index, or None when there is not one edit."""
    mismatch_index: int | None = None

    for index, query_character in enumerate(query):
        if query_character != sentence[start + index]:
            if mismatch_index is not None:
                return None
            mismatch_index = index

    return mismatch_index


def find_query_extra_character_index(
    query: str,
    sentence: str,
    start: int,
) -> int | None:
    """Return the index of one character that can be removed from query."""
    sentence_index = 0
    query_length = len(query)

    while (
        sentence_index < query_length - 1
        and query[sentence_index] == sentence[start + sentence_index]
    ):
        sentence_index += 1

    if sentence_index == query_length - 1:
        return query_length - 1

    query_index = sentence_index + 1
    while query_index < query_length:
        if query[query_index] != sentence[start + query_index - 1]:
            return None
        query_index += 1

    return sentence_index


def find_sentence_extra_character_index(
    query: str,
    sentence: str,
    start: int,
) -> int | None:
    """Return the index of one character that can be removed from sentence."""
    query_index = 0
    query_length = len(query)

    while (
        query_index < query_length
        and query[query_index] == sentence[start + query_index]
    ):
        query_index += 1

    if query_index == query_length:
        return query_length

    sentence_index = query_index + 1
    while sentence_index <= query_length:
        if query[sentence_index - 1] != sentence[start + sentence_index]:
            return None
        sentence_index += 1

    return query_index


def calculate_best_match(query: str, sentence: str) -> int | None:
    """Score a query against one sentence, allowing at most one edit."""
    normalized_query = normalize(query)
    normalized_sentence = normalize(sentence)

    if not normalized_query or not normalized_sentence:
        return None

    query_length = len(normalized_query)

    if normalized_query in normalized_sentence:
        return query_length * 2

    best_score: int | None = None

    # One substituted character. The comparison stops as soon as it finds a
    # second mismatch, without allocating a substring for every window.
    for start in range(len(normalized_sentence) - query_length + 1):
        mismatch_index = find_single_substitution_index(
            normalized_query,
            normalized_sentence,
            start,
        )
        if mismatch_index is not None:
            score = query_length * 2 - get_substitution_penalty(mismatch_index)
            best_score = score if best_score is None else max(best_score, score)

    # One extra character in the query.
    if query_length > 1:
        for start in range(len(normalized_sentence) - query_length + 2):
            extra_index = find_query_extra_character_index(
                normalized_query,
                normalized_sentence,
                start,
            )
            if extra_index is not None:
                score = (query_length - 1) * 2 - get_missing_or_added_penalty(extra_index)
                best_score = score if best_score is None else max(best_score, score)

    # One missing character in the query.
    for start in range(len(normalized_sentence) - query_length):
        extra_index = find_sentence_extra_character_index(
            normalized_query,
            normalized_sentence,
            start,
        )
        if extra_index is not None:
            score = query_length * 2 - get_missing_or_added_penalty(extra_index)
            best_score = score if best_score is None else max(best_score, score)

    return best_score
