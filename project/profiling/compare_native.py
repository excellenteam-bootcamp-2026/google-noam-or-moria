"""Compare Python and C++ indexes on the same corpus sample."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.autocomplete import select_indexed_completions, select_native_completions
from src.indexer import build_search_data
from src.loader import load_sentences
from src.models import SearchData
from src.native_index import NativeIndex


def measure(operation):
    started = perf_counter()
    result = operation()
    return result, perf_counter() - started


def result_signature(results):
    return [
        (
            result.completed_sentence,
            result.source_text,
            result.offset,
            result.score,
        )
        for result in results
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus")
    parser.add_argument("--sample-size", type=int, default=100_000)
    arguments = parser.parse_args()

    all_sentences = load_sentences(arguments.corpus)
    sentences = all_sentences[: arguments.sample_size]
    metadata = SearchData(
        {sentence.sentence_id: sentence for sentence in sentences},
        {},
        {},
        {},
    )

    python_data, python_build_seconds = measure(
        lambda: build_search_data(sentences)
    )
    native_index, native_build_seconds = measure(
        lambda: NativeIndex.from_search_data(metadata)
    )

    long_sentence = next(
        sentence.normalized_sentence
        for sentence in sentences
        if len(sentence.normalized_sentence.split()) >= 10
    )
    long_query = " ".join(long_sentence.split()[:10])
    queries = [
        "a",
        "th",
        "the",
        long_query,
        "x" + long_query[1:],
    ]

    print(f"sentences={len(sentences):,}")
    print(f"python_build_seconds={python_build_seconds:.6f}")
    print(f"native_build_seconds={native_build_seconds:.6f}")

    try:
        for query in queries:
            python_results, python_seconds = measure(
                lambda: select_indexed_completions(query, python_data)
            )
            native_results, native_seconds = measure(
                lambda: select_native_completions(
                    query,
                    metadata,
                    native_index,
                )
            )
            equal = result_signature(python_results) == result_signature(native_results)
            print(
                f"query={query[:45]!r} "
                f"python_ms={python_seconds * 1000:.3f} "
                f"native_ms={native_seconds * 1000:.3f} "
                f"equal={equal}"
            )
            if not equal:
                raise AssertionError(f"Different results for query {query!r}")
    finally:
        native_index.close()


if __name__ == "__main__":
    main()
