from __future__ import annotations

from pathlib import Path

from . import normalization
from .models import SentenceData


def load_sentences(root_path: str) -> list[SentenceData]:
    """Load sentences from every text file below ``root_path``.

    Each non-empty line is stored with its original text, normalized text,
    source path, and one-based line number.
    """
    root = Path(root_path)

    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")

    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    sentences: list[SentenceData] = []
    text_files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".txt"
    )

    for file_path in text_files:
        with file_path.open("r", encoding="utf-8-sig") as source_file:
            for offset, line in enumerate(source_file, start=1):
                original_sentence = line.rstrip("\r\n")

                if not original_sentence.strip():
                    continue

                sentences.append(
                    SentenceData(
                        sentence_id=len(sentences),
                        original_sentence=original_sentence,
                        normalized_sentence=normalization.normalize(
                            original_sentence
                        ),
                        source_path=str(file_path),
                        offset=offset,
                    )
                )

    return sentences
