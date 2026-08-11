from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.loader import load_sentences


class LoadSentencesTests(TestCase):
    def test_loads_nested_text_files_and_preserves_metadata(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested_directory = root / "topic" / "python"
            nested_directory.mkdir(parents=True)

            first_file = root / "first.txt"
            first_file.write_text(
                "Hello, World!\n\n  Keep original spacing  \n",
                encoding="utf-8",
            )
            second_file = nested_directory / "second.TXT"
            second_file.write_text("Nested sentence\n", encoding="utf-8")
            (root / "ignored.md").write_text(
                "This is not a text file\n", encoding="utf-8"
            )

            sentences = load_sentences(str(root))

            self.assertEqual(len(sentences), 3)
            self.assertEqual(sentences[0].sentence_id, 0)
            self.assertEqual(sentences[0].original_sentence, "Hello, World!")
            self.assertEqual(sentences[0].normalized_sentence, "hello world")
            self.assertEqual(sentences[0].source_path, str(first_file))
            self.assertEqual(sentences[0].offset, 1)

            self.assertEqual(
                sentences[1].original_sentence, "  Keep original spacing  "
            )
            self.assertEqual(sentences[1].sentence_id, 1)
            self.assertEqual(
                sentences[1].normalized_sentence, "keep original spacing"
            )
            self.assertEqual(sentences[1].offset, 3)

            self.assertEqual(sentences[2].sentence_id, 2)
            self.assertEqual(sentences[2].original_sentence, "Nested sentence")
            self.assertEqual(sentences[2].source_path, str(second_file))
            self.assertEqual(sentences[2].offset, 1)

    def test_empty_directory_returns_empty_list(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            self.assertEqual(load_sentences(temporary_directory), [])

    def test_identical_sentences_in_different_files_get_unique_ids(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first_file = root / "first.txt"
            second_file = root / "second.txt"
            first_file.write_text("Same sentence\n", encoding="utf-8")
            second_file.write_text("Same sentence\n", encoding="utf-8")

            sentences = load_sentences(str(root))

            self.assertEqual([sentence.sentence_id for sentence in sentences], [0, 1])
            self.assertEqual(
                [sentence.source_path for sentence in sentences],
                [str(first_file), str(second_file)],
            )

    def test_missing_directory_raises_file_not_found(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing"

            with self.assertRaises(FileNotFoundError):
                load_sentences(str(missing_path))

    def test_file_path_raises_not_a_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "sentences.txt"
            file_path.write_text("Sentence\n", encoding="utf-8")

            with self.assertRaises(NotADirectoryError):
                load_sentences(str(file_path))
