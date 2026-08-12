"""Persistence for the offline N-gram indexes using Protocol Buffers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
from typing import Iterable

from google.protobuf.message import DecodeError

from .models import SearchData, SentenceData
from .search_index_pb2 import PostingList
from .search_index_pb2 import SearchIndex


class InvalidSearchIndexError(ValueError):
    """Raised when a saved index is corrupt or incompatible."""


def file_hash(path: str | Path) -> str:
    """Calculate a SHA-256 hash without loading the entire file into RAM."""
    digest = hashlib.sha256()

    with Path(path).open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _add_postings(
    target: Iterable[PostingList],
    index: dict[str, list[int]],
) -> None:
    for gram in sorted(index):
        posting = target.add(gram=gram)
        posting.sentence_ids.extend(index[gram])


def search_data_to_protobuf(
    search_data: SearchData,
    archive_hash: str,
) -> SearchIndex:
    """Convert the in-memory model to its portable protobuf representation."""
    protobuf_index = SearchIndex(source_archive_hash=archive_hash)

    for sentence_id in sorted(search_data.sentences_by_id):
        sentence = search_data.sentences_by_id[sentence_id]
        protobuf_index.sentences.add(
            sentence_id=sentence.sentence_id,
            original_sentence=sentence.original_sentence,
            normalized_sentence=sentence.normalized_sentence,
            source_path=sentence.source_path,
            offset=sentence.offset,
        )

    _add_postings(protobuf_index.unigrams, search_data.unigram_index)
    _add_postings(protobuf_index.bigrams, search_data.bigram_index)
    _add_postings(protobuf_index.trigrams, search_data.trigram_index)
    return protobuf_index


def _restore_index(postings: Iterable[PostingList]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}

    for posting in postings:
        if posting.gram in result:
            raise InvalidSearchIndexError(
                f"Duplicate posting list for gram: {posting.gram!r}"
            )
        result[posting.gram] = list(posting.sentence_ids)

    return result


def protobuf_to_search_data(protobuf_index: SearchIndex) -> SearchData:
    """Restore SearchData while preserving list-based posting lists."""
    sentences_by_id: dict[int, SentenceData] = {}

    for sentence in protobuf_index.sentences:
        if sentence.sentence_id in sentences_by_id:
            raise InvalidSearchIndexError(
                f"Duplicate sentence ID: {sentence.sentence_id}"
            )
        sentences_by_id[sentence.sentence_id] = SentenceData(
            sentence_id=sentence.sentence_id,
            original_sentence=sentence.original_sentence,
            normalized_sentence=sentence.normalized_sentence,
            source_path=sentence.source_path,
            offset=sentence.offset,
        )

    return SearchData(
        sentences_by_id=sentences_by_id,
        unigram_index=_restore_index(protobuf_index.unigrams),
        bigram_index=_restore_index(protobuf_index.bigrams),
        trigram_index=_restore_index(protobuf_index.trigrams),
    )


def save_search_data(
    search_data: SearchData,
    archive_hash: str,
    index_path: str | Path,
) -> None:
    """Serialize the complete index atomically so partial files are avoided."""
    destination = Path(index_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = search_data_to_protobuf(search_data, archive_hash)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload.SerializeToString())
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_search_data(index_path: str | Path) -> tuple[SearchData, str]:
    """Load SearchData and the hash of the archive it was built from."""
    protobuf_index = SearchIndex()

    try:
        protobuf_index.ParseFromString(Path(index_path).read_bytes())
    except (OSError, DecodeError) as error:
        raise InvalidSearchIndexError(
            f"Could not load protobuf index: {index_path}"
        ) from error

    return (
        protobuf_to_search_data(protobuf_index),
        protobuf_index.source_archive_hash,
    )
