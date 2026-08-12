"""Chunked Protocol Buffer persistence for large sentence corpora."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator
from pathlib import Path

from src.generated import corpus_pb2
from src.loader import iter_sentences
from src.models import SentenceData


FORMAT_VERSION = 1
DEFAULT_CHUNK_SIZE = 50_000
CHUNK_PATTERN = "corpus-*.pb"


def _append_record(
    chunk: corpus_pb2.CorpusChunk,
    sentence: SentenceData,
) -> None:
    record = chunk.sentences.add()
    record.sentence_id = sentence.sentence_id
    record.original_sentence = sentence.original_sentence
    record.normalized_sentence = sentence.normalized_sentence
    record.source_path = sentence.source_path
    record.offset = sentence.offset


def _write_chunk(
    chunk: corpus_pb2.CorpusChunk,
    output_directory: Path,
) -> Path:
    output_path = output_directory / f"corpus-{chunk.chunk_number:05d}.pb"
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing corpus chunk: {output_path}"
        )
    output_path.write_bytes(chunk.SerializeToString())
    return output_path


def save_corpus_chunks(
    sentences: Iterable[SentenceData],
    output_directory: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> list[Path]:
    """Serialize sentences to bounded-size, numbered Protobuf files."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    chunk = corpus_pb2.CorpusChunk(
        format_version=FORMAT_VERSION,
        chunk_number=0,
    )

    for sentence in sentences:
        _append_record(chunk, sentence)
        if len(chunk.sentences) >= chunk_size:
            written_paths.append(_write_chunk(chunk, directory))
            chunk = corpus_pb2.CorpusChunk(
                format_version=FORMAT_VERSION,
                chunk_number=chunk.chunk_number + 1,
            )

    if chunk.sentences:
        written_paths.append(_write_chunk(chunk, directory))

    return written_paths


def load_corpus_chunks(
    input_directory: str | Path,
) -> Iterator[SentenceData]:
    """Read and validate numbered Protobuf chunks one at a time."""

    directory = Path(input_directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a corpus chunk directory: {directory}")

    paths = sorted(directory.glob(CHUNK_PATTERN))
    for expected_number, path in enumerate(paths):
        chunk = corpus_pb2.CorpusChunk()
        chunk.ParseFromString(path.read_bytes())

        if chunk.format_version != FORMAT_VERSION:
            raise ValueError(
                f"Unsupported corpus format {chunk.format_version} in {path}"
            )
        if chunk.chunk_number != expected_number:
            raise ValueError(
                f"Expected chunk {expected_number}, found {chunk.chunk_number}"
            )

        for record in chunk.sentences:
            yield SentenceData(
                sentence_id=record.sentence_id,
                original_sentence=record.original_sentence,
                normalized_sentence=record.normalized_sentence,
                source_path=record.source_path,
                offset=record.offset,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a text corpus to chunked Protocol Buffers",
    )
    parser.add_argument("corpus", help="Root directory containing text files")
    parser.add_argument("output", help="New or empty output directory")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    arguments = parser.parse_args()

    paths = save_corpus_chunks(
        iter_sentences(arguments.corpus),
        arguments.output,
        arguments.chunk_size,
    )
    print(f"Wrote {len(paths)} Protobuf corpus chunks to {arguments.output}")


if __name__ == "__main__":
    main()
