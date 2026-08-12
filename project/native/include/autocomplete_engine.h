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
AUTOCOMPLETE_API const char* autocomplete_engine_last_error();

}
