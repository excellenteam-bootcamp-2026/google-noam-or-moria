"""Python bridge to the optional C++ N-gram candidate engine."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Iterable

from src.models import SearchData, SentenceData


DEFAULT_LIBRARY_PATH = (
    Path(__file__).resolve().parents[1]
    / "native"
    / "build"
    / "Release"
    / "autocomplete_native.dll"
)


class NativeEngineError(RuntimeError):
    """Raised when the native autocomplete engine reports an error."""


class NativeIndex:
    """Own a C++ index and expose Python-friendly search methods."""

    def __init__(self, library_path: str | Path | None = None) -> None:
        path = Path(library_path or DEFAULT_LIBRARY_PATH)
        if not path.is_file():
            raise FileNotFoundError(
                f"Native autocomplete library was not found: {path}. "
                "Build project/native with CMake first."
            )

        self._library = ctypes.CDLL(str(path))
        self._configure_signatures()
        self._handle = self._library.autocomplete_engine_create()
        if not self._handle:
            self._raise_last_error("Could not create native autocomplete engine")

    @classmethod
    def from_search_data(
        cls,
        search_data: SearchData,
        library_path: str | Path | None = None,
    ) -> "NativeIndex":
        engine = cls(library_path)
        try:
            engine.add_sentences(search_data.sentences_by_id.values())
        except Exception:
            engine.close()
            raise
        return engine

    def _configure_signatures(self) -> None:
        uint32_pointer = ctypes.POINTER(ctypes.c_uint32)

        self._library.autocomplete_engine_create.argtypes = []
        self._library.autocomplete_engine_create.restype = ctypes.c_void_p
        self._library.autocomplete_engine_destroy.argtypes = [ctypes.c_void_p]
        self._library.autocomplete_engine_destroy.restype = None
        self._library.autocomplete_engine_add_sentence.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        self._library.autocomplete_engine_add_sentence.restype = ctypes.c_int
        self._library.autocomplete_engine_find_exact_top_k.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            uint32_pointer,
        ]
        self._library.autocomplete_engine_find_exact_top_k.restype = ctypes.c_size_t
        self._library.autocomplete_engine_find_fuzzy_candidates.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(uint32_pointer),
        ]
        self._library.autocomplete_engine_find_fuzzy_candidates.restype = ctypes.c_size_t
        self._library.autocomplete_engine_free_ids.argtypes = [uint32_pointer]
        self._library.autocomplete_engine_free_ids.restype = None
        self._library.autocomplete_engine_last_error.argtypes = []
        self._library.autocomplete_engine_last_error.restype = ctypes.c_char_p

    def _raise_last_error(self, fallback: str) -> None:
        encoded_error = self._library.autocomplete_engine_last_error()
        message = encoded_error.decode("utf-8") if encoded_error else fallback
        raise NativeEngineError(message)

    def add_sentences(self, sentences: Iterable[SentenceData]) -> None:
        self._ensure_open()
        for sentence in sentences:
            added = self._library.autocomplete_engine_add_sentence(
                self._handle,
                sentence.sentence_id,
                sentence.normalized_sentence.encode("utf-8"),
                self._sort_key(sentence).encode("utf-8"),
            )
            if not added:
                self._raise_last_error(
                    f"Could not add sentence {sentence.sentence_id}"
                )

    @staticmethod
    def _sort_key(sentence: SentenceData) -> str:
        """Match the complete deterministic ordering used by Python."""

        separator = "\x1f"
        return separator.join(
            (
                sentence.original_sentence.casefold(),
                sentence.original_sentence,
                sentence.source_path,
                f"{sentence.offset:020d}",
            )
        )

    def find_exact_top_k(self, normalized_query: str, k: int = 5) -> list[int]:
        self._ensure_open()
        if k <= 0 or not normalized_query:
            return []

        output = (ctypes.c_uint32 * k)()
        count = self._library.autocomplete_engine_find_exact_top_k(
            self._handle,
            normalized_query.encode("utf-8"),
            k,
            output,
        )
        self._check_error()
        return list(output[:count])

    def find_fuzzy_candidate_ids(self, normalized_query: str) -> set[int]:
        self._ensure_open()
        if not normalized_query:
            return set()

        output = ctypes.POINTER(ctypes.c_uint32)()
        count = self._library.autocomplete_engine_find_fuzzy_candidates(
            self._handle,
            normalized_query.encode("utf-8"),
            ctypes.byref(output),
        )
        self._check_error()
        try:
            return {output[index] for index in range(count)}
        finally:
            if output:
                self._library.autocomplete_engine_free_ids(output)

    def _check_error(self) -> None:
        encoded_error = self._library.autocomplete_engine_last_error()
        if encoded_error:
            self._raise_last_error("Native autocomplete operation failed")

    def _ensure_open(self) -> None:
        if not self._handle:
            raise NativeEngineError("Native autocomplete engine is closed")

    def close(self) -> None:
        if self._handle:
            self._library.autocomplete_engine_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> "NativeIndex":
        return self

    def __exit__(self, *ignored: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
