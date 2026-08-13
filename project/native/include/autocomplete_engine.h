#pragma once

#include <cstddef>
#include <cstdint>

#if defined(_WIN32)
#  if defined(AUTOCOMPLETE_NATIVE_EXPORTS)
#    define AUTOCOMPLETE_API __declspec(dllexport)
#  else
#    define AUTOCOMPLETE_API __declspec(dllimport)
#  endif
#else
#  define AUTOCOMPLETE_API
#endif

extern "C" {

using autocomplete_engine_handle = void*;

AUTOCOMPLETE_API autocomplete_engine_handle autocomplete_engine_create();
AUTOCOMPLETE_API void autocomplete_engine_destroy(
    autocomplete_engine_handle handle
);

AUTOCOMPLETE_API int autocomplete_engine_add_sentence(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id,
    const char* normalized_sentence_utf8,
    const char* alphabetical_sort_key_utf8
);

AUTOCOMPLETE_API int autocomplete_engine_add_sentence_full(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id,
    const char* original_sentence_utf8,
    const char* normalized_sentence_utf8,
    const char* source_path_utf8,
    std::uint32_t offset,
    const char* alphabetical_sort_key_utf8
);

AUTOCOMPLETE_API int autocomplete_engine_load_corpus_directory(
    autocomplete_engine_handle handle,
    const char* directory_path_utf8
);

// Persist and restore the fully built native index. The fingerprint is
// calculated by Python from the protobuf chunk metadata and prevents an index
// built for one corpus from being used with another corpus.
AUTOCOMPLETE_API int autocomplete_engine_save_index_cache(
    autocomplete_engine_handle handle,
    const char* cache_path_utf8,
    const char* corpus_fingerprint_utf8
);
AUTOCOMPLETE_API int autocomplete_engine_load_index_cache(
    autocomplete_engine_handle handle,
    const char* cache_path_utf8,
    const char* expected_fingerprint_utf8
);

AUTOCOMPLETE_API std::size_t autocomplete_engine_sentence_count(
    autocomplete_engine_handle handle
);

AUTOCOMPLETE_API std::size_t autocomplete_engine_find_exact_top_k(
    autocomplete_engine_handle handle,
    const char* normalized_query_utf8,
    std::size_t k,
    std::uint32_t* output_ids
);

AUTOCOMPLETE_API std::size_t autocomplete_engine_find_fuzzy_candidates(
    autocomplete_engine_handle handle,
    const char* normalized_query_utf8,
    std::uint32_t** output_ids
);

AUTOCOMPLETE_API void autocomplete_engine_free_ids(std::uint32_t* ids);
AUTOCOMPLETE_API const char* autocomplete_engine_sentence_original(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
);
AUTOCOMPLETE_API const char* autocomplete_engine_sentence_normalized(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
);
AUTOCOMPLETE_API const char* autocomplete_engine_sentence_source(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
);
AUTOCOMPLETE_API std::uint32_t autocomplete_engine_sentence_offset(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
);
AUTOCOMPLETE_API const char* autocomplete_engine_last_error();

}
