from unittest.mock import patch

from src.main import print_completions, update_query
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
