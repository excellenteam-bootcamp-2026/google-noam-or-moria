from __future__ import annotations
import string
import re
from models import SearchData


# Import normalize from the same directory
from normalization import normalize

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



def create_ngrams(text: str, n: int) -> set[str]:
    # Return an empty set if the text is shorter than n
    if len(text) < n:
        return set()
    
    # Generate all contiguous substrings of length n
    ngrams = set()
    for i in range(len(text) - n + 1):
        ngrams.add(text[i : i + n])
        
    return ngrams


def find_candidate_ids(normalized_query: str, search_data: SearchData) -> set[int]:
    query_len = len(normalized_query)
    
    # Return empty set for empty query
    if query_len == 0:
        return set()
        
    # Length 1: Return all sentence IDs
    if query_len == 1:
        return set(search_data.sentences_by_id.keys())
        
    # Determine the n-gram size and target index based on query length
    if query_len == 2 or query_len == 3:
        n = 1
        target_index = search_data.unigram_index
    elif query_len == 4 or query_len == 5:
        n = 2
        target_index = search_data.bigram_index
    else:
        n = 3
        target_index = search_data.trigram_index
        
    # Extract n-grams from the query
    query_ngrams = create_ngrams(normalized_query, n)
    
    # Perform a set union operation across all matching sets
    candidate_ids = set()
    for gram in query_ngrams:
        if gram in target_index:
            candidate_ids.update(target_index[gram])
            
    return candidate_ids