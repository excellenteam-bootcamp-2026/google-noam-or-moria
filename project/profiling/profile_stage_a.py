r"""Profile the Python implementation before moving a component to C++.

Run from the ``project`` directory::

    python profiling/profile_stage_a.py C:\path\to\corpus

The corpus is loaded once without profiling. Index construction is then
profiled on a representative sample, while online searches are profiled on
the complete index. This avoids multiplying the expensive file-I/O phase by
the overhead that cProfile adds to every Python function call.
"""

from __future__ import annotations

import argparse
import cProfile
import io
from pathlib import Path
import pstats
import sys
from time import perf_counter
from typing import Callable, TypeVar


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.autocomplete import select_indexed_completions
from src.indexer import build_search_data
from src.loader import load_sentences


T = TypeVar("T")


def profiled(label: str, operation: Callable[[], T], limit: int = 20) -> T:
    """Run ``operation`` and print its most expensive cumulative calls."""

    profiler = cProfile.Profile()
    started = perf_counter()
    result = profiler.runcall(operation)
    elapsed = perf_counter() - started

    report = io.StringIO()
    stats = pstats.Stats(profiler, stream=report)
    stats.strip_dirs().sort_stats("cumulative").print_stats(limit)
    print(f"\n=== {label}: {elapsed:.3f} seconds ===")
    print(report.getvalue())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile the Stage A Python autocomplete implementation",
    )
    parser.add_argument("corpus", help="Root directory containing text files")
    parser.add_argument(
        "--index-sample-size",
        type=int,
        default=100_000,
        help="Number of loaded sentences used for index-build profiling",
    )
    arguments = parser.parse_args()

    started = perf_counter()
    sentences = load_sentences(arguments.corpus)
    load_seconds = perf_counter() - started
    print(
        f"Loaded {len(sentences):,} sentences in {load_seconds:.3f} seconds",
        flush=True,
    )

    sample_size = min(arguments.index_sample_size, len(sentences))
    profiled(
        f"build_search_data ({sample_size:,} sentences)",
        lambda: build_search_data(sentences[:sample_size]),
    )

    started = perf_counter()
    search_data = build_search_data(sentences)
    full_index_seconds = perf_counter() - started
    print(
        f"Built the full index in {full_index_seconds:.3f} seconds",
        flush=True,
    )

    sample_sentence = next(
        sentence.normalized_sentence
        for sentence in sentences
        if len(sentence.normalized_sentence.split()) >= 15
    )
    ten_words = " ".join(sample_sentence.split()[:10])
    queries = [
        "a",
        "th",
        "the",
        ten_words,
        "x" + ten_words[1:],
        ten_words[:-1] + ("x" if ten_words[-1] != "x" else "y"),
        "this phrase should not occur anywhere in the complete archive xyzq",
    ]

    def run_queries() -> list[tuple[str, int]]:
        return [
            (query, len(select_indexed_completions(query, search_data)))
            for query in queries
        ]

    query_results = profiled("seven representative online queries", run_queries)
    for query, result_count in query_results:
        print(f"results={result_count} chars={len(query):3d} query={query!r}")


if __name__ == "__main__":
    main()
