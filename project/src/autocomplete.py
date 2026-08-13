"""Selection and state management for autocomplete suggestions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from heapq import nsmallest

from src.matcher import calculate_best_match
from src.models import AutoCompleteData, SearchData, SentenceData


_search_data: SearchData | None = None
_native_index: object | None = None


def _scored_sentence_rank(
    scored_sentence: tuple[SentenceData, int],
) -> tuple[object, ...]:
    """Return the single deterministic ordering used by every search path."""

    sentence, score = scored_sentence
    return (
        -score,
        sentence.original_sentence.casefold(),
        sentence.original_sentence,
        sentence.source_path,
        sentence.offset,
    )


def _top_completions(
    scored_sentences: Iterable[tuple[SentenceData, int]],
    k: int,
) -> list[AutoCompleteData]:
    """Keep only the best K records and materialize public results for them."""

    if k <= 0:
        return []
    best = nsmallest(k, scored_sentences, key=_scored_sentence_rank)
    return [_to_completion(sentence, score) for sentence, score in best]


def _to_completion(sentence: SentenceData, score: int) -> AutoCompleteData:
    """Convert one internal sentence record to the required public result."""

    return AutoCompleteData(
        completed_sentence=sentence.original_sentence,
        source_text=sentence.source_path,
        offset=sentence.offset,
        score=score,
    )


def _build_scored_completions(
    candidate_scores: Mapping[int, int | None],
    get_sentence: Callable[[int], SentenceData],
    k: int,
) -> list[AutoCompleteData]:
    """Rank scored IDs using a sentence provider from either backend."""

    def scored_sentences() -> Iterable[tuple[SentenceData, int]]:
        for sentence_id, score in candidate_scores.items():
            if score is not None:
                yield get_sentence(sentence_id), score

    return _top_completions(scored_sentences(), k)


def initialize(root_path: str | None = None, use_native: bool = False) -> None:
    """Build and store all data required by the online completion function."""

    global _native_index
    if _native_index is not None:
        _native_index.close()
        _native_index = None

    if use_native:
        from src.indexer import load_configured_sentences
        from src.models import SearchData
        from src.native_index import NativeIndex

        sentences = load_configured_sentences(root_path)
        search_data = SearchData(
            sentences_by_id={
                sentence.sentence_id: sentence for sentence in sentences
            },
            unigram_index={},
            bigram_index={},
            trigram_index={},
        )
        _native_index = NativeIndex.from_search_data(search_data)
    else:
        from src.indexer import initialize as build_search_data

        search_data = build_search_data(root_path)

    set_search_data(search_data)


def initialize_from_protobuf(
    directory: str,
    cache_path: str | None = None,
) -> None:
    """Load a native cache or build it once from chunked protobuf data."""

    from src.native_index import NativeIndex

    global _native_index
    if _native_index is not None:
        _native_index.close()
    _native_index = NativeIndex.from_protobuf_directory(
        directory,
        cache_path=cache_path,
    )

    set_search_data(SearchData({}, {}, {}, {}))


def set_search_data(search_data: SearchData) -> None:
    """Store the data prepared by the offline initialization stage."""

    global _search_data
    _search_data = search_data


def get_best_k_completions(prefix: str) -> list[AutoCompleteData]:
    """Return the five best completions from the initialized search index."""

    if _search_data is None:
        raise RuntimeError("Autocomplete data has not been initialized")

    if _native_index is not None:
        return select_native_completions(prefix, _native_index, k=5)

    return select_indexed_completions(prefix, _search_data, k=5)


def select_native_completions(
    query: str,
    native_index: object,
    k: int = 5,
) -> list[AutoCompleteData]:
    """Search through the C++ index and keep scoring/output in Python."""

    from src.normalization import normalize

    normalized_query = normalize(query)
    if k <= 0 or not normalized_query:
        return []

    exact_ids = native_index.find_exact_top_k(normalized_query, k)
    exact_score = len(normalized_query) * 2
    exact_id_set = set(exact_ids)

    def scored_sentences() -> Iterable[tuple[SentenceData, int]]:
        for sentence_id in exact_ids:
            sentence = native_index.get_sentence(sentence_id)
            yield sentence, exact_score

        if len(exact_ids) >= k:
            return

        fuzzy_ids = native_index.find_fuzzy_candidate_ids(normalized_query)
        for sentence_id in fuzzy_ids - exact_id_set:
            # Fetch each native record once: it is used both for scoring and,
            # when valid, for the public result returned to Python.
            sentence = native_index.get_sentence(sentence_id)
            score = calculate_best_match(
                normalized_query,
                sentence.normalized_sentence,
            )
            if score is not None:
                yield sentence, score

    return _top_completions(scored_sentences(), k)


def build_native_completions(
    candidate_scores: Mapping[int, int | None],
    native_index: object,
    k: int = 5,
) -> list[AutoCompleteData]:
    """Build public results by copying only selected records from C++."""

    return _build_scored_completions(
        candidate_scores,
        native_index.get_sentence,
        k,
    )


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

    return _build_scored_completions(
        candidate_scores,
        search_data.sentences_by_id.__getitem__,
        k,
    )


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

    def scored_sentences() -> Iterable[tuple[SentenceData, int]]:
        for sentence_id in exact_ids:
            sentence = search_data.sentences_by_id[sentence_id]
            yield sentence, exact_score

        fuzzy_candidate_ids = find_fuzzy_candidates(normalized_query, search_data)
        # Exact-index false positives may still be valid one-edit matches, so
        # only candidates already verified as exact are excluded here.
        additional_ids = fuzzy_candidate_ids - exact_matches.keys()
        for sentence_id in additional_ids:
            sentence = search_data.sentences_by_id[sentence_id]
            score = calculate_best_match(
                normalized_query,
                sentence.normalized_sentence,
            )
            if score is not None:
                yield sentence, score

    return _top_completions(scored_sentences(), k)
