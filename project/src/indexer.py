from collections import Counter

from .loader import load_sentences
from .models import SearchData, SentenceData


def create_ngrams(text: str, n: int) -> set[str]:
    """Return the unique contiguous character N-grams in ``text``."""
    if n <= 0:
        raise ValueError("n must be a positive integer")

    return {text[index : index + n] for index in range(len(text) - n + 1)}


def build_search_data(sentences: list[SentenceData]) -> SearchData:
    """Build the offline lookup data used by the autocomplete service."""
    sentences_by_id: dict[int, SentenceData] = {}
    unigram_index: dict[str, list[int]] = {}
    bigram_index: dict[str, list[int]] = {}
    trigram_index: dict[str, list[int]] = {}

    indexes = {
        1: unigram_index,
        2: bigram_index,
        3: trigram_index,
    }

    for sentence in sentences:
        if sentence.sentence_id in sentences_by_id:
            raise ValueError(f"Duplicate sentence ID: {sentence.sentence_id}")

        sentences_by_id[sentence.sentence_id] = sentence

        for n, index in indexes.items():
            for gram in create_ngrams(sentence.normalized_sentence, n):
                index.setdefault(gram, []).append(sentence.sentence_id)

    return SearchData(
        sentences_by_id=sentences_by_id,
        unigram_index=unigram_index,
        bigram_index=bigram_index,
        trigram_index=trigram_index,
    )


def initialize(root_path: str) -> SearchData:
    """Load the text corpus and build all offline search indexes."""
    return build_search_data(load_sentences(root_path))


def find_exact_candidate_ids(
    normalized_query: str,
    search_data: SearchData,
) -> set[int]:
    """Return candidates from the query's rarest exact-match N-gram."""
    query_length = len(normalized_query)

    if query_length == 0:
        return set()

    if query_length == 1:
        return set(search_data.unigram_index.get(normalized_query, []))

    if query_length == 2:
        return set(search_data.bigram_index.get(normalized_query, []))

    posting_lists = [
        search_data.trigram_index.get(gram, [])
        for gram in create_ngrams(normalized_query, 3)
    ]

    smallest_posting = min(posting_lists, key=len)
    return set(smallest_posting)


def find_candidate_ids(
    normalized_query: str,
    search_data: SearchData,
) -> set[int]:
    """Return candidate sentence IDs without excluding one-edit matches."""
    query_length = len(normalized_query)

    if query_length == 0:
        return set()

    if query_length == 1:
        # For a one-character query, staged search assumes no typo so the
        # scoring engine does not receive the entire corpus.
        return set(search_data.unigram_index.get(normalized_query, []))

    if query_length <= 3:
        n = 1
        index = search_data.unigram_index
    elif query_length <= 5:
        n = 2
        index = search_data.bigram_index
    else:
        n = 3
        index = search_data.trigram_index

    query_ngrams = create_ngrams(normalized_query, n)
    match_counts: Counter[int] = Counter()

    for gram in query_ngrams:
        for sentence_id in index.get(gram, []):
            match_counts[sentence_id] += 1

    # One edit can affect at most ``n`` adjacent N-grams. Requiring all other
    # grams greatly reduces false candidates without excluding one-edit matches.
    minimum_shared = max(1, len(query_ngrams) - n)

    return {
        sentence_id
        for sentence_id, count in match_counts.items()
        if count >= minimum_shared
    }
