"""Command-line interface for the autocomplete project."""

from __future__ import annotations

from collections.abc import Callable

from src.autocomplete import (
    get_candidate_completions,
    get_best_k_completions,
    initialize,
    initialize_from_protobuf,
)
from src.models import AutoCompleteData


def update_query(current_query: str, typed_text: str) -> str:
    """Return the next query after typing text or requesting a reset."""

    if typed_text == "#":
        return ""

    return current_query + typed_text


def print_completions(
    query: str,
    provider: Callable[[str], list[AutoCompleteData]] | None = None,
) -> list[AutoCompleteData]:
    """Print and return the best completions for the current query."""

    completions = (provider or get_best_k_completions)(query)
    if not completions:
        print("No suggestions found.")
        return []

    print(f"Here are {len(completions)} suggestions:")
    for index, completion in enumerate(completions, start=1):
        print(
            f"{index}. {completion.completed_sentence} "
            f"({completion.source_text}, line {completion.offset}, "
            f"score {completion.score})"
        )
    return completions


def parse_selection_command(typed_text: str) -> int | None:
    """Parse an explicit ':select N' command into a zero-based index."""

    command, separator, raw_number = typed_text.strip().partition(" ")
    if command.casefold() != ":select" or not separator:
        return None
    try:
        selection = int(raw_number) - 1
    except ValueError:
        return None
    return selection if selection >= 0 else None


def run_cli(
    root_path: str | None = None,
    use_native: bool = False,
    protobuf_directory: str | None = None,
    cache_path: str | None = None,
    personalized: bool = False,
    user_id: str = "demo-user",
    history_path: str = ".autocomplete-history.json",
    gemini_model: str = "gemini-2.5-flash-lite",
) -> None:
    """Load the data and run the interactive autocomplete prompt."""

    if protobuf_directory:
        initialize_from_protobuf(protobuf_directory, cache_path=cache_path)
    else:
        initialize(root_path, use_native=use_native)

    personalized_service = None
    completion_provider = get_best_k_completions
    if personalized:
        from src.personalization import (
            GeminiCandidateReranker,
            GeminiJsonOrderModel,
            JsonSearchHistoryStore,
            PersonalizedAutocomplete,
        )

        personalized_service = PersonalizedAutocomplete(
            get_candidate_completions,
            JsonSearchHistoryStore(history_path),
            GeminiCandidateReranker(GeminiJsonOrderModel(model=gemini_model)),
        )
        completion_provider = lambda query: personalized_service.complete(
            user_id,
            query,
        )

    current_query = ""
    last_query = ""
    last_completions: list[AutoCompleteData] = []

    print("The system is ready. Enter your text:")
    if personalized:
        print(
            "Personalization is enabled. Use ':select N' to save a chosen "
            "suggestion, and '#' to reset the query."
        )
    try:
        while True:
            typed_text = input(current_query)

            first_token = typed_text.strip().casefold().partition(" ")[0]
            if first_token == ":select":
                selection = parse_selection_command(typed_text)
                if selection is None or selection >= len(last_completions):
                    print("Invalid selection. Use ':select N' from the last results.")
                    continue
                if personalized_service is None:
                    print("Selection history requires --personalized.")
                    continue
                chosen = last_completions[selection]
                personalized_service.record_selection(user_id, last_query, chosen)
                print(f"Saved selection: {chosen.completed_sentence}")
                current_query = ""
                last_query = ""
                last_completions = []
                continue

            if typed_text == "#":
                current_query = update_query(current_query, typed_text)
                last_query = ""
                last_completions = []
                print("Query reset.")
                continue

            current_query = update_query(current_query, typed_text)
            if current_query:
                last_query = current_query
                last_completions = print_completions(
                    current_query,
                    completion_provider,
                )
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sentence autocomplete")
    parser.add_argument(
        "root_path",
        nargs="?",
        help="Root folder containing text files",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="Use the compiled C++ candidate index",
    )
    parser.add_argument(
        "--protobuf",
        metavar="DIRECTORY",
        help="Load chunked Protobuf corpus directly in C++",
    )
    parser.add_argument(
        "--cache",
        metavar="PATH",
        help="Optional path for the persistent native index cache",
    )
    parser.add_argument(
        "--personalized",
        action="store_true",
        help="Rerank candidates using explicit search history and Gemini",
    )
    parser.add_argument(
        "--user-id",
        default="demo-user",
        help="Local history profile used by personalized mode",
    )
    parser.add_argument(
        "--history",
        default=".autocomplete-history.json",
        help="Path to the local Stage C history file",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-2.5-flash-lite",
        help="Google Gemini model used for candidate reranking",
    )
    arguments = parser.parse_args()
    run_cli(
        arguments.root_path,
        use_native=arguments.native,
        protobuf_directory=arguments.protobuf,
        cache_path=arguments.cache,
        personalized=arguments.personalized,
        user_id=arguments.user_id,
        history_path=arguments.history,
        gemini_model=arguments.gemini_model,
    )
