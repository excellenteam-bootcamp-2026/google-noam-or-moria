"""Selection and state management for autocomplete suggestions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from heapq import nsmallest

from src.matcher import calculate_best_match
from src.models import AutoCompleteData, SearchData, SentenceData


_sentences: list[SentenceData] = []


def set_sentences(sentences: Iterable[SentenceData]) -> None:
    """Replace the sentences used by the public completion function.

    This small function keeps the online completion API independent from the
    offline loader and also makes the module easy to test.
    """

    global _sentences
    _sentences = list(sentences)


def select_best_completions(
    query: str,
    sentences: Iterable[SentenceData],
    k: int = 5,
) -> list[AutoCompleteData]:
    """Return up to ``k`` highest-scoring completions for ``query``.

    The matcher owns normalization and score calculation.  This function owns
    filtering, conversion to the required output model, and deterministic
    ordering.
    """

    if k <= 0 or not query:
        return []

    matches: list[AutoCompleteData] = []
    for sentence in sentences:
        score = calculate_best_match(query, sentence.normalized_sentence)
        if score is None:
            continue

        matches.append(
            AutoCompleteData(
                completed_sentence=sentence.original_sentence,
                source_text=sentence.source_path,
                offset=sentence.offset,
                score=score,
            )
        )

    matches.sort(
        key=lambda result: (
            -result.score,
            result.completed_sentence.casefold(),
            result.completed_sentence,
            result.source_text,
            result.offset,
        )
    )
    return matches[:k]


def get_best_k_completions(prefix: str) -> list[AutoCompleteData]:
    """Return the five best completions from the initialized sentence data."""

    return select_best_completions(prefix, _sentences, k=5)


def build_best_completions(
    candidate_scores: Mapping[int, int | None],
    search_data: SearchData,
    k: int = 5,
) -> list[AutoCompleteData]:
    """Build and rank results returned by the future indexed search.

    ``candidate_scores`` contains only sentence IDs selected by Or's N-gram
    index, paired with scores calculated by Noam's matcher.  This function is
    independent of both implementations, so it can be completed and tested
    before their branches are ready.
    """

    if k <= 0:
        return []

    matches: list[AutoCompleteData] = []
    for sentence_id, score in candidate_scores.items():
        if score is None:
            continue

        sentence = search_data.sentences_by_id[sentence_id]
        matches.append(
            AutoCompleteData(
                completed_sentence=sentence.original_sentence,
                source_text=sentence.source_path,
                offset=sentence.offset,
                score=score,
            )
        )

    matches.sort(
        key=lambda result: (
            -result.score,
            result.completed_sentence.casefold(),
            result.completed_sentence,
            result.source_text,
            result.offset,
        )
    )
    return matches[:k]


def select_indexed_completions(
    query: str,
    search_data: SearchData,
    k: int = 5,
) -> list[AutoCompleteData]:
    """Run the complete online search flow over indexed sentence data.

    Or's index narrows the corpus to candidate sentence IDs. Noam's matcher
    then validates and scores only those candidates, and this module ranks the
    best results for display.
    """

    if k <= 0:
        return []

    # These modules are supplied by the teammates' branches. Keeping the
    # imports here lets this branch's independent unit tests run before merge.
    from src.indexer import find_candidate_ids, find_exact_candidate_ids
    from src.normalization import normalize

    normalized_query = normalize(query)
    if not normalized_query:
        return []

    return select_staged_completions(
        normalized_query,
        search_data,
        find_exact_candidate_ids,
        find_candidate_ids,
        k,
    )


def select_staged_completions(
    normalized_query: str,
    search_data: SearchData,
    find_exact_candidates: Callable[[str, SearchData], set[int]],
    find_fuzzy_candidates: Callable[[str, SearchData], set[int]],
    k: int = 5,
) -> list[AutoCompleteData]:
    """Search exact candidates first and expand to fuzzy ones only if needed."""

    if k <= 0 or not normalized_query:
        return []

    exact_score = len(normalized_query) * 2
    exact_candidate_ids = find_exact_candidates(normalized_query, search_data)
    exact_ids = nsmallest(
        k,
        (
            sentence_id
            for sentence_id in exact_candidate_ids
            if normalized_query
            in search_data.sentences_by_id[sentence_id].normalized_sentence
        ),
        key=lambda sentence_id: (
            search_data.sentences_by_id[sentence_id].original_sentence.casefold(),
            search_data.sentences_by_id[sentence_id].original_sentence,
            search_data.sentences_by_id[sentence_id].source_path,
            search_data.sentences_by_id[sentence_id].offset,
        ),
    )
    exact_matches = {sentence_id: exact_score for sentence_id in exact_ids}
    if len(exact_matches) >= k:
        return build_best_completions(exact_matches, search_data, k)

    candidate_scores: dict[int, int | None] = dict(exact_matches)
    fuzzy_candidate_ids = find_fuzzy_candidates(normalized_query, search_data)
    # Exact-index false positives may still be valid one-edit matches, so only
    # candidates already verified as exact are excluded from fuzzy scoring.
    additional_ids = fuzzy_candidate_ids - exact_matches.keys()
    for sentence_id in additional_ids:
        candidate_scores[sentence_id] = calculate_best_match(
            normalized_query,
            search_data.sentences_by_id[sentence_id].normalized_sentence,
        )

    return build_best_completions(candidate_scores, search_data, k)
