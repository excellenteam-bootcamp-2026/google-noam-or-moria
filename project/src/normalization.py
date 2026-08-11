import string
import re

def normalize(text: str) -> str:
    # Convert all characters to lowercase
    text = text.lower()
    
    # Remove all punctuation using string translation
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Replace multiple spaces with a single space and trim edges
    return re.sub(r'\s+', ' ', text).strip()