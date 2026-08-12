#include "autocomplete_engine.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <queue>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kMaxFuzzyGrams = 10;
thread_local std::string last_error;

struct Sentence {
    std::uint32_t id;
    std::string normalized;
    std::string sort_key;
};

using PostingList = std::vector<std::uint32_t>;
using Index = std::unordered_map<std::string, PostingList>;

std::vector<std::string> create_ngrams(const std::string& text, std::size_t n) {
    std::unordered_set<std::string> unique_grams;
    if (n == 0 || text.size() < n) {
        return {};
    }

    unique_grams.reserve(text.size() - n + 1);
    for (std::size_t position = 0; position + n <= text.size(); ++position) {
        unique_grams.insert(text.substr(position, n));
    }
    return {unique_grams.begin(), unique_grams.end()};
}

class Engine {
public:
    void add_sentence(
        std::uint32_t id,
        std::string normalized,
        std::string sort_key
    ) {
        if (position_by_id_.find(id) != position_by_id_.end()) {
            throw std::invalid_argument("duplicate sentence ID");
        }

        position_by_id_[id] = sentences_.size();
        sentences_.push_back({id, std::move(normalized), std::move(sort_key)});
        const std::string& text = sentences_.back().normalized;

        add_to_index(unigram_index_, text, 1, id);
        add_to_index(bigram_index_, text, 2, id);
        add_to_index(trigram_index_, text, 3, id);
    }

    std::vector<std::uint32_t> exact_top_k(
        const std::string& query,
        std::size_t k
    ) const {
        if (query.empty() || k == 0) {
            return {};
        }

        const PostingList* candidates = exact_posting(query);
        if (candidates == nullptr) {
            return {};
        }

        const auto better = [this](std::uint32_t left, std::uint32_t right) {
            const Sentence& left_sentence = sentence(left);
            const Sentence& right_sentence = sentence(right);
            if (left_sentence.sort_key != right_sentence.sort_key) {
                return left_sentence.sort_key < right_sentence.sort_key;
            }
            return left < right;
        };

        std::priority_queue<
            std::uint32_t,
            std::vector<std::uint32_t>,
            decltype(better)
        > best(better);

        for (const std::uint32_t id : *candidates) {
            if (sentence(id).normalized.find(query) == std::string::npos) {
                continue;
            }

            if (best.size() < k) {
                best.push(id);
            } else if (better(id, best.top())) {
                best.pop();
                best.push(id);
            }
        }

        std::vector<std::uint32_t> result;
        result.reserve(best.size());
        while (!best.empty()) {
            result.push_back(best.top());
            best.pop();
        }
        std::sort(result.begin(), result.end(), better);
        return result;
    }

    std::vector<std::uint32_t> fuzzy_candidates(
        const std::string& query
    ) const {
        if (query.empty()) {
            return {};
        }

        std::size_t n = 3;
        const Index* index = &trigram_index_;
        if (query.size() <= 3) {
            n = 1;
            index = &unigram_index_;
        } else if (query.size() <= 5) {
            n = 2;
            index = &bigram_index_;
        }

        std::vector<std::string> grams = create_ngrams(query, n);
        if (n == 3 && grams.size() > kMaxFuzzyGrams) {
            std::partial_sort(
                grams.begin(),
                grams.begin() + kMaxFuzzyGrams,
                grams.end(),
                [index](const std::string& left, const std::string& right) {
                    return posting_size(*index, left) < posting_size(*index, right);
                }
            );
            grams.resize(kMaxFuzzyGrams);
        }

        std::unordered_map<std::uint32_t, std::size_t> match_counts;
        for (const std::string& gram : grams) {
            const auto found = index->find(gram);
            if (found == index->end()) {
                continue;
            }
            for (const std::uint32_t id : found->second) {
                ++match_counts[id];
            }
        }

        const std::size_t minimum_shared = std::max<std::size_t>(
            1,
            grams.size() > n ? grams.size() - n : 0
        );
        std::vector<std::uint32_t> result;
        result.reserve(match_counts.size());
        for (const auto& [id, count] : match_counts) {
            if (count >= minimum_shared) {
                result.push_back(id);
            }
        }
        return result;
    }

private:
    static void add_to_index(
        Index& index,
        const std::string& text,
        std::size_t n,
        std::uint32_t id
    ) {
        for (const std::string& gram : create_ngrams(text, n)) {
            index[gram].push_back(id);
        }
    }

    static std::size_t posting_size(const Index& index, const std::string& gram) {
        const auto found = index.find(gram);
        return found == index.end() ? 0 : found->second.size();
    }

    const Sentence& sentence(std::uint32_t id) const {
        return sentences_.at(position_by_id_.at(id));
    }

    const PostingList* exact_posting(const std::string& query) const {
        if (query.size() == 1) {
            return find_posting(unigram_index_, query);
        }
        if (query.size() == 2) {
            return find_posting(bigram_index_, query);
        }

        const PostingList* smallest = nullptr;
        for (const std::string& gram : create_ngrams(query, 3)) {
            const PostingList* posting = find_posting(trigram_index_, gram);
            if (posting == nullptr) {
                return nullptr;
            }
            if (smallest == nullptr || posting->size() < smallest->size()) {
                smallest = posting;
            }
        }
        return smallest;
    }

    static const PostingList* find_posting(
        const Index& index,
        const std::string& gram
    ) {
        const auto found = index.find(gram);
        return found == index.end() ? nullptr : &found->second;
    }

    std::vector<Sentence> sentences_;
    std::unordered_map<std::uint32_t, std::size_t> position_by_id_;
    Index unigram_index_;
    Index bigram_index_;
    Index trigram_index_;
};

Engine& engine_from(autocomplete_engine_handle handle) {
    if (handle == nullptr) {
        throw std::invalid_argument("engine handle is null");
    }
    return *static_cast<Engine*>(handle);
}

template <typename Operation, typename Fallback>
auto protect(Operation operation, Fallback fallback) -> decltype(operation()) {
    try {
        last_error.clear();
        return operation();
    } catch (const std::exception& error) {
        last_error = error.what();
    } catch (...) {
        last_error = "unknown native error";
    }
    return fallback;
}

}  // namespace

extern "C" {

autocomplete_engine_handle autocomplete_engine_create() {
    return protect(
        []() -> autocomplete_engine_handle { return new Engine(); },
        nullptr
    );
}

void autocomplete_engine_destroy(autocomplete_engine_handle handle) {
    delete static_cast<Engine*>(handle);
}

int autocomplete_engine_add_sentence(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id,
    const char* normalized_sentence_utf8,
    const char* alphabetical_sort_key_utf8
) {
    return protect(
        [&]() {
            if (normalized_sentence_utf8 == nullptr ||
                alphabetical_sort_key_utf8 == nullptr) {
                throw std::invalid_argument("sentence text is null");
            }
            engine_from(handle).add_sentence(
                sentence_id,
                normalized_sentence_utf8,
                alphabetical_sort_key_utf8
            );
            return 1;
        },
        0
    );
}

std::size_t autocomplete_engine_find_exact_top_k(
    autocomplete_engine_handle handle,
    const char* normalized_query_utf8,
    std::size_t k,
    std::uint32_t* output_ids
) {
    return protect(
        [&]() {
            if (normalized_query_utf8 == nullptr || (k > 0 && output_ids == nullptr)) {
                throw std::invalid_argument("invalid exact-search argument");
            }
            const auto result = engine_from(handle).exact_top_k(
                normalized_query_utf8,
                k
            );
            std::copy(result.begin(), result.end(), output_ids);
            return result.size();
        },
        std::size_t{0}
    );
}

std::size_t autocomplete_engine_find_fuzzy_candidates(
    autocomplete_engine_handle handle,
    const char* normalized_query_utf8,
    std::uint32_t** output_ids
) {
    return protect(
        [&]() {
            if (normalized_query_utf8 == nullptr || output_ids == nullptr) {
                throw std::invalid_argument("invalid fuzzy-search argument");
            }
            *output_ids = nullptr;
            const auto result = engine_from(handle).fuzzy_candidates(
                normalized_query_utf8
            );
            if (result.empty()) {
                return std::size_t{0};
            }

            const std::size_t byte_count = result.size() * sizeof(std::uint32_t);
            auto* copied = static_cast<std::uint32_t*>(std::malloc(byte_count));
            if (copied == nullptr) {
                throw std::bad_alloc();
            }
            std::memcpy(copied, result.data(), byte_count);
            *output_ids = copied;
            return result.size();
        },
        std::size_t{0}
    );
}

void autocomplete_engine_free_ids(std::uint32_t* ids) {
    std::free(ids);
}

const char* autocomplete_engine_last_error() {
    return last_error.c_str();
}

}
