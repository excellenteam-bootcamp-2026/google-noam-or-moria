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
    unigram_index: dict[str, set[int]] = {}
    bigram_index: dict[str, set[int]] = {}
    trigram_index: dict[str, set[int]] = {}

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
                index.setdefault(gram, set()).add(sentence.sentence_id)

    return SearchData(
        sentences_by_id=sentences_by_id,
        unigram_index=unigram_index,
        bigram_index=bigram_index,
        trigram_index=trigram_index,
    )


def initialize(root_path: str) -> SearchData:
    """Load the text corpus and build all offline search indexes."""
    return build_search_data(load_sentences(root_path))


def find_candidate_ids(
    normalized_query: str,
    search_data: SearchData,
) -> set[int]:
    """Return candidate sentence IDs without excluding one-edit matches."""
    query_length = len(normalized_query)

    if query_length == 0:
        return set()

    if query_length == 1:
        # A single incorrect character gives the index no reliable gram to use.
        return set(search_data.sentences_by_id)

    if query_length <= 3:
        n = 1
        index = search_data.unigram_index
    elif query_length <= 5:
        n = 2
        index = search_data.bigram_index
    else:
        n = 3
        index = search_data.trigram_index

    candidate_ids: set[int] = set()
    for gram in create_ngrams(normalized_query, n):
        candidate_ids.update(index.get(gram, set()))

    return candidate_ids
