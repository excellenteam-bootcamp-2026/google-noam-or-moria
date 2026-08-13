import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.main import (
    parse_selection_command,
    print_completions,
    run_cli,
    update_query,
)
from src.models import AutoCompleteData


def test_typing_continues_the_previous_query() -> None:
    assert update_query("hello", " world") == "hello world"


def test_hash_resets_the_query() -> None:
    assert update_query("hello world", "#") == ""


def test_empty_typed_text_keeps_the_current_query() -> None:
    assert update_query("hello", "") == "hello"


def test_prints_all_required_completion_fields(capsys) -> None:
    completion = AutoCompleteData(
        completed_sentence="The cat sleeps.",
        source_text="animals.txt",
        offset=7,
        score=12,
    )

    with patch(
        "src.main.get_best_k_completions",
        return_value=[completion],
    ):
        print_completions("cat")

    output = capsys.readouterr().out
    assert "The cat sleeps." in output
    assert "animals.txt" in output
    assert "line 7" in output
    assert "score 12" in output


def test_prints_message_when_there_are_no_suggestions(capsys) -> None:
    with patch("src.main.get_best_k_completions", return_value=[]):
        print_completions("missing")

    assert capsys.readouterr().out == "No suggestions found.\n"


def test_cli_loads_protobuf_directly_and_exits_cleanly(capsys) -> None:
    with patch("src.main.initialize_from_protobuf") as protobuf_initialize:
        with patch("src.main.initialize") as text_initialize:
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                run_cli(protobuf_directory="chunks")

    protobuf_initialize.assert_called_once_with("chunks", cache_path=None)
    text_initialize.assert_not_called()
    assert "Goodbye." in capsys.readouterr().out


def test_cli_passes_native_mode_to_text_initialization() -> None:
    with patch("src.main.initialize") as initialize:
        with patch("builtins.input", side_effect=EOFError):
            run_cli("corpus", use_native=True)

    initialize.assert_called_once_with("corpus", use_native=True)


def test_cli_hash_resets_before_continuing(capsys) -> None:
    with patch("src.main.initialize"):
        with patch("builtins.input", side_effect=["#", KeyboardInterrupt]):
            run_cli("corpus")

    assert "Query reset." in capsys.readouterr().out


def test_selection_command_is_explicit_and_one_based() -> None:
    assert parse_selection_command(":select 1") == 0
    assert parse_selection_command(":SELECT 5") == 4
    assert parse_selection_command("1") is None
    assert parse_selection_command(":select invalid") is None


def test_personalized_cli_persists_an_explicit_selection(capsys) -> None:
    completion = AutoCompleteData("The cat sleeps", "animals.txt", 7, 12)

    with tempfile.TemporaryDirectory() as directory:
        history_path = Path(directory) / "history.json"
        with patch("src.main.initialize"):
            with patch(
                "src.main.get_candidate_completions",
                return_value=[completion],
            ):
                with patch(
                    "builtins.input",
                    side_effect=["cat", ":select 1", KeyboardInterrupt],
                ):
                    run_cli(
                        "corpus",
                        personalized=True,
                        user_id="noam",
                        history_path=str(history_path),
                    )

        saved = json.loads(history_path.read_text(encoding="utf-8"))

    assert saved["noam"][0] == {
        "query": "cat",
        "selected_sentence": "The cat sleeps",
    }
    assert "Saved selection: The cat sleeps" in capsys.readouterr().out
