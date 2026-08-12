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

    # One substituted character.
    for start in range(len(normalized_sentence) - query_length + 1):
        candidate = normalized_sentence[start : start + query_length]
        mismatches = [
            index
            for index in range(query_length)
            if normalized_query[index] != candidate[index]
        ]
        if len(mismatches) == 1:
            score = query_length * 2 - get_substitution_penalty(mismatches[0])
            best_score = score if best_score is None else max(best_score, score)

    # One extra character in the query.
    if query_length > 1:
        for start in range(len(normalized_sentence) - query_length + 2):
            candidate = normalized_sentence[start : start + query_length - 1]
            for index in range(query_length):
                edited_query = normalized_query[:index] + normalized_query[index + 1 :]
                if edited_query == candidate:
                    score = (query_length - 1) * 2 - get_missing_or_added_penalty(index)
                    best_score = score if best_score is None else max(best_score, score)

    # One missing character in the query.
    for start in range(len(normalized_sentence) - query_length):
        candidate = normalized_sentence[start : start + query_length + 1]
        for index in range(query_length + 1):
            edited_candidate = candidate[:index] + candidate[index + 1 :]
            if normalized_query == edited_candidate:
                score = query_length * 2 - get_missing_or_added_penalty(index)
                best_score = score if best_score is None else max(best_score, score)

    return best_score
