"""Command-line interface for the autocomplete project."""

from src.autocomplete import select_indexed_completions
from src.models import SearchData


def update_query(current_query: str, typed_text: str) -> str:
    """Return the next query after typing text or requesting a reset."""

    if typed_text == "#":
        return ""

    return current_query + typed_text


def print_completions(query: str, search_data: SearchData) -> None:
    """Print the best completions for the current query."""

    completions = select_indexed_completions(query, search_data)
    if not completions:
        print("No suggestions found.")
        return

    print(f"Here are {len(completions)} suggestions:")
    for index, completion in enumerate(completions, start=1):
        print(
            f"{index}. {completion.completed_sentence} "
            f"({completion.source_text}, line {completion.offset}, "
            f"score {completion.score})"
        )


def run_cli(root_path: str) -> None:
    """Load the data and run the interactive autocomplete prompt."""

    # Imported here because the indexer is supplied by Or's branch.
    from src.indexer import initialize

    search_data = initialize(root_path)
    current_query = ""

    print("The system is ready. Enter your text:")
    while True:
        typed_text = input(current_query)
        if typed_text == "#":
            current_query = update_query(current_query, typed_text)
            print("Query reset.")
            continue

        current_query = update_query(current_query, typed_text)
        if current_query:
            print_completions(current_query, search_data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sentence autocomplete")
    parser.add_argument("root_path", help="Root folder containing text files")
    arguments = parser.parse_args()
    run_cli(arguments.root_path)
