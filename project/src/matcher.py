from __future__ import annotations
import string
import re

# Import normalize from the single source of truth
from src.normalization import normalize


def get_substitution_penalty(error_index: int) -> int:
    penalties = [5, 4, 3, 2]
    if error_index < len(penalties):
        return penalties[error_index]
    return 1


def get_missing_or_added_penalty(error_index: int) -> int:
    penalties = [10, 8, 6, 4]
    if error_index < len(penalties):
        return penalties[error_index]
    return 2


def calculate_best_match(query: str, sentence: str) -> int | None:
    norm_query = normalize(query)
    norm_sentence = normalize(sentence)

    if not norm_query or not norm_sentence:
        return None

    n = len(norm_query)

    # Option 1: Exact match
    if norm_query in norm_sentence:
        return n * 2

    best_score = None

    # Option 2: Substitution (same length match with 1 character difference)
    for i in range(len(norm_sentence) - n + 1):
        sub = norm_sentence[i : i + n]
        mismatches = [idx for idx in range(n) if norm_query[idx] != sub[idx]]

        if len(mismatches) == 1:
            err_idx = mismatches[0]
            score = (n * 2) - get_substitution_penalty(err_idx)
            if best_score is None or score > best_score:
                best_score = score

    # Option 3: Character added in query (query is 1 character longer)
    if n > 1:
        for i in range(len(norm_sentence) - (n - 1) + 1):
            sub = norm_sentence[i : i + n - 1]
            for idx in range(n):
                # Remove 1 character from query at idx and compare with sub
                modified_query = norm_query[:idx] + norm_query[idx + 1 :]
                if modified_query == sub:
                    # Matched characters in sentence is n - 1
                    base_score = (n - 1) * 2
                    score = base_score - get_missing_or_added_penalty(idx)
                    if best_score is None or score > best_score:
                        best_score = score

    # Option 4: Character missing in query (query is 1 character shorter)
    for i in range(len(norm_sentence) - (n + 1) + 1):
        sub = norm_sentence[i : i + n + 1]
        for idx in range(n + 1):
            # Remove 1 character from sentence window at idx and compare with query
            modified_sub = sub[:idx] + sub[idx + 1 :]
            if norm_query == modified_sub:
                base_score = n * 2
                score = base_score - get_missing_or_added_penalty(idx)
                if best_score is None or score > best_score:
                    best_score = score

    return best_score