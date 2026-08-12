from pathlib import Path
from collections.abc import Iterator

from . import normalization
from .models import SentenceData


def load_sentences(root_path: str) -> list[SentenceData]:
    """Load sentences from every text file below ``root_path``.

    Each non-empty line is stored with its original text, normalized text,
    source path, and one-based line number.
    """
    return list(iter_sentences(root_path))


def iter_sentences(root_path: str) -> Iterator[SentenceData]:
    """Yield corpus sentences one at a time for large-data conversion."""

    root = Path(root_path)

    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")

    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    text_files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".txt"
    )

    sentence_id = 0
    for file_path in text_files:
        with file_path.open("r", encoding="utf-8-sig") as source_file:
            for offset, line in enumerate(source_file, start=1):
                original_sentence = line.rstrip("\r\n")

                if not original_sentence.strip():
                    continue

                yield SentenceData(
                    sentence_id=sentence_id,
                    original_sentence=original_sentence,
                    normalized_sentence=normalization.normalize(
                        original_sentence
                    ),
                    source_path=str(file_path),
                    offset=offset,
                )
                sentence_id += 1
