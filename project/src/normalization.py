import re
import string

def normalize(text: str) -> str:
    """Normalize case, punctuation, and whitespace for searching.

    Punctuation is replaced with whitespace rather than removed.  This keeps
    adjacent words separated: ``"be,that"`` and ``"be that"`` normalize to
    the same value.
    """
    text = text.lower()

    text = text.translate(str.maketrans({character: " " for character in string.punctuation}))
    return re.sub(r'\s+', ' ', text).strip()
