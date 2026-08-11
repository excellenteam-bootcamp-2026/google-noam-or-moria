from dataclasses import dataclass

@dataclass
class SentenceData:
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