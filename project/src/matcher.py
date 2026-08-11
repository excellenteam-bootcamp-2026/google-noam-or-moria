from src.models import SentenceData

def normalize(text: str) -> str:
    """
    Normalizes the input text by removing punctuation,
    lowercasing, and fixing multiple spaces.
    """
    pass


def calculate_best_match(query: str, sentence: str) -> int | None:
    """
    Calculates the best match score between a normalized query
    and a normalized sentence. 
    Returns None if more than one edit is required.
    """
    pass