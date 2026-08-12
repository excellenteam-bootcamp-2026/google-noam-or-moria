#include "autocomplete_engine.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <set>

int main() {
    autocomplete_engine_handle engine = autocomplete_engine_create();
    assert(engine != nullptr);

    assert(autocomplete_engine_add_sentence(
        engine, 10, "the dog runs", "the dog runs"
    ));
    assert(autocomplete_engine_add_sentence(
        engine, 20, "the cat sleeps", "the cat sleeps"
    ));
    assert(autocomplete_engine_add_sentence(
        engine, 30, "a bird flies", "a bird flies"
    ));

    std::uint32_t exact_ids[2] = {};
    const std::size_t exact_count = autocomplete_engine_find_exact_top_k(
        engine, "the", 2, exact_ids
    );
    assert(exact_count == 2);
    assert(exact_ids[0] == 20);
    assert(exact_ids[1] == 10);

    std::uint32_t* fuzzy_ids = nullptr;
    const std::size_t fuzzy_count = autocomplete_engine_find_fuzzy_candidates(
        engine, "thf cat", &fuzzy_ids
    );
    const std::set<std::uint32_t> fuzzy_result(
        fuzzy_ids,
        fuzzy_ids + fuzzy_count
    );
    assert(fuzzy_result.count(20) == 1);
    autocomplete_engine_free_ids(fuzzy_ids);

    autocomplete_engine_destroy(engine);
    std::cout << "native engine tests passed\n";
    return 0;
}
