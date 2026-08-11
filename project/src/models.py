from __future__ import annotations
from dataclasses import dataclass
# Enable modern type hinting syntax in Python 3.8

@dataclass
class SentenceData:
    # A unique identifier used by the N-gram indexes
    sentence_id: int
    # The original sentence exactly as it appears in the file
    original_sentence: str
    # The sentence after removing punctuation and standardizing spaces
    normalized_sentence: str
    # The file path where this sentence was found
    source_path: str
    # The line number in the source file
    offset: int


@dataclass
class AutoCompleteData:
    # The matched sentence to display to the user
    completed_sentence: str
    # The source file path
    source_text: str
    # The line number
    offset: int
    # The calculated match score based on the penalty rules
    score: int


@dataclass
class SearchData:
    """All data prepared during the offline initialization stage."""

    # Fast access from an index result to the sentence and its metadata
    sentences_by_id: dict[int, SentenceData]
    # N-gram -> IDs of sentences containing that N-gram
    unigram_index: dict[str, set[int]]
    bigram_index: dict[str, set[int]]
    trigram_index: dict[str, set[int]]
