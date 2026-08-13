#include "autocomplete_engine.h"
#include "corpus.pb.h"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
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
    std::string original;
    std::string normalized;
    std::string source;
    std::uint32_t offset;
    std::string sort_key;
};

using PostingList = std::vector<std::uint32_t>;
using Index = std::unordered_map<std::string, PostingList>;

constexpr std::array<char, 8> kCacheMagic = {'A', 'C', 'I', 'D', 'X', '0', '1', '\0'};
constexpr std::uint32_t kCacheFormatVersion = 1;

template <typename Value>
void write_value(std::ostream& output, const Value& value) {
    output.write(reinterpret_cast<const char*>(&value), sizeof(value));
    if (!output) {
        throw std::runtime_error("could not write native index cache");
    }
}

template <typename Value>
Value read_value(std::istream& input) {
    Value value{};
    input.read(reinterpret_cast<char*>(&value), sizeof(value));
    if (!input) {
        throw std::runtime_error("native index cache is truncated");
    }
    return value;
}

void write_string(std::ostream& output, const std::string& value) {
    if (value.size() > std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error("native index cache string is too large");
    }
    write_value(output, static_cast<std::uint32_t>(value.size()));
    output.write(value.data(), static_cast<std::streamsize>(value.size()));
    if (!output) {
        throw std::runtime_error("could not write native index cache string");
    }
}

std::string read_string(std::istream& input) {
    const auto size = read_value<std::uint32_t>(input);
    std::string value(size, '\0');
    input.read(value.data(), static_cast<std::streamsize>(size));
    if (!input) {
        throw std::runtime_error("native index cache string is truncated");
    }
    return value;
}

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
        std::string original,
        std::string normalized,
        std::string source,
        std::uint32_t offset,
        std::string sort_key
    ) {
        if (position_by_id_.find(id) != position_by_id_.end()) {
            throw std::invalid_argument("duplicate sentence ID");
        }

        position_by_id_[id] = sentences_.size();
        sentences_.push_back({
            id,
            std::move(original),
            std::move(normalized),
            std::move(source),
            offset,
            std::move(sort_key),
        });
        const std::string& text = sentences_.back().normalized;

        add_to_index(unigram_index_, text, 1, id);
        add_to_index(bigram_index_, text, 2, id);
        add_to_index(trigram_index_, text, 3, id);
    }

    void load_corpus_directory(const std::filesystem::path& directory) {
        if (!std::filesystem::is_directory(directory)) {
            throw std::invalid_argument("protobuf corpus directory does not exist");
        }

        std::vector<std::filesystem::path> chunk_paths;
        for (const auto& entry : std::filesystem::directory_iterator(directory)) {
            const std::string filename = entry.path().filename().string();
            if (entry.is_regular_file() &&
                filename.rfind("corpus-", 0) == 0 &&
                entry.path().extension() == ".pb") {
                chunk_paths.push_back(entry.path());
            }
        }
        std::sort(chunk_paths.begin(), chunk_paths.end());

        for (std::size_t expected = 0; expected < chunk_paths.size(); ++expected) {
            std::ifstream input(chunk_paths[expected], std::ios::binary);
            google_autocomplete::CorpusChunk chunk;
            if (!input || !chunk.ParseFromIstream(&input)) {
                throw std::runtime_error("could not parse protobuf corpus chunk");
            }
            if (chunk.format_version() != 1) {
                throw std::runtime_error("unsupported protobuf corpus version");
            }
            if (chunk.chunk_number() != expected) {
                throw std::runtime_error("protobuf corpus chunk sequence is invalid");
            }

            for (const auto& record : chunk.sentences()) {
                add_sentence(
                    record.sentence_id(),
                    record.original_sentence(),
                    record.normalized_sentence(),
                    record.source_path(),
                    record.offset(),
                    record.casefolded_sentence().empty()
                        ? record.original_sentence()
                        : record.casefolded_sentence()
                );
            }
        }
    }

    void save_index_cache(
        const std::filesystem::path& cache_path,
        const std::string& corpus_fingerprint
    ) const {
        if (cache_path.empty()) {
            throw std::invalid_argument("native index cache path is empty");
        }

        if (!cache_path.parent_path().empty()) {
            std::filesystem::create_directories(cache_path.parent_path());
        }
        const std::filesystem::path temporary_path = cache_path.string() + ".tmp";
        std::ofstream output(temporary_path, std::ios::binary | std::ios::trunc);
        if (!output) {
            throw std::runtime_error("could not create native index cache");
        }

        output.write(kCacheMagic.data(), static_cast<std::streamsize>(kCacheMagic.size()));
        write_value(output, kCacheFormatVersion);
        write_string(output, corpus_fingerprint);
        write_value(output, static_cast<std::uint64_t>(sentences_.size()));
        for (const Sentence& sentence : sentences_) {
            write_value(output, sentence.id);
            write_string(output, sentence.original);
            write_string(output, sentence.normalized);
            write_string(output, sentence.source);
            write_value(output, sentence.offset);
            write_string(output, sentence.sort_key);
        }
        write_index(output, unigram_index_);
        write_index(output, bigram_index_);
        write_index(output, trigram_index_);
        output.close();
        if (!output) {
            throw std::runtime_error("could not finish native index cache");
        }

        std::error_code ignored;
        std::filesystem::remove(cache_path, ignored);
        std::filesystem::rename(temporary_path, cache_path);
    }

    void load_index_cache(
        const std::filesystem::path& cache_path,
        const std::string& expected_fingerprint
    ) {
        if (!sentences_.empty()) {
            throw std::logic_error("cannot load a cache into a populated native index");
        }

        std::ifstream input(cache_path, std::ios::binary);
        if (!input) {
            throw std::runtime_error("could not open native index cache");
        }
        std::array<char, kCacheMagic.size()> magic{};
        input.read(magic.data(), static_cast<std::streamsize>(magic.size()));
        if (!input || magic != kCacheMagic) {
            throw std::runtime_error("native index cache has an invalid header");
        }
        if (read_value<std::uint32_t>(input) != kCacheFormatVersion) {
            throw std::runtime_error("native index cache has an unsupported version");
        }
        if (read_string(input) != expected_fingerprint) {
            throw std::runtime_error("native index cache belongs to another corpus");
        }

        Engine restored;
        const auto sentence_count = read_value<std::uint64_t>(input);
        restored.sentences_.reserve(static_cast<std::size_t>(sentence_count));
        for (std::uint64_t position = 0; position < sentence_count; ++position) {
            Sentence sentence{
                read_value<std::uint32_t>(input),
                read_string(input),
                read_string(input),
                read_string(input),
                read_value<std::uint32_t>(input),
                read_string(input),
            };
            if (!restored.position_by_id_.emplace(
                    sentence.id,
                    restored.sentences_.size()
                ).second) {
                throw std::runtime_error("native index cache has duplicate sentence IDs");
            }
            restored.sentences_.push_back(std::move(sentence));
        }
        restored.unigram_index_ = read_index(input);
        restored.bigram_index_ = read_index(input);
        restored.trigram_index_ = read_index(input);

        sentences_ = std::move(restored.sentences_);
        position_by_id_ = std::move(restored.position_by_id_);
        unigram_index_ = std::move(restored.unigram_index_);
        bigram_index_ = std::move(restored.bigram_index_);
        trigram_index_ = std::move(restored.trigram_index_);
    }

    std::size_t sentence_count() const {
        return sentences_.size();
    }

    const Sentence& sentence_by_id(std::uint32_t id) const {
        return sentence(id);
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
            if (left_sentence.original != right_sentence.original) {
                return left_sentence.original < right_sentence.original;
            }
            if (left_sentence.source != right_sentence.source) {
                return left_sentence.source < right_sentence.source;
            }
            if (left_sentence.offset != right_sentence.offset) {
                return left_sentence.offset < right_sentence.offset;
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
    static void write_index(std::ostream& output, const Index& index) {
        write_value(output, static_cast<std::uint64_t>(index.size()));
        std::vector<std::string> grams;
        grams.reserve(index.size());
        for (const auto& entry : index) {
            grams.push_back(entry.first);
        }
        std::sort(grams.begin(), grams.end());

        for (const std::string& gram : grams) {
            const PostingList& posting = index.at(gram);
            write_string(output, gram);
            write_value(output, static_cast<std::uint64_t>(posting.size()));
            output.write(
                reinterpret_cast<const char*>(posting.data()),
                static_cast<std::streamsize>(posting.size() * sizeof(std::uint32_t))
            );
            if (!output) {
                throw std::runtime_error("could not write native index posting list");
            }
        }
    }

    static Index read_index(std::istream& input) {
        const auto gram_count = read_value<std::uint64_t>(input);
        Index index;
        index.reserve(static_cast<std::size_t>(gram_count));
        for (std::uint64_t position = 0; position < gram_count; ++position) {
            std::string gram = read_string(input);
            const auto posting_size = read_value<std::uint64_t>(input);
            PostingList posting(static_cast<std::size_t>(posting_size));
            input.read(
                reinterpret_cast<char*>(posting.data()),
                static_cast<std::streamsize>(posting.size() * sizeof(std::uint32_t))
            );
            if (!input || !index.emplace(std::move(gram), std::move(posting)).second) {
                throw std::runtime_error("native index cache has an invalid posting list");
            }
        }
        return index;
    }

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
                alphabetical_sort_key_utf8,
                normalized_sentence_utf8,
                "",
                0,
                alphabetical_sort_key_utf8
            );
            return 1;
        },
        0
    );
}

int autocomplete_engine_add_sentence_full(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id,
    const char* original_sentence_utf8,
    const char* normalized_sentence_utf8,
    const char* source_path_utf8,
    std::uint32_t offset,
    const char* alphabetical_sort_key_utf8
) {
    return protect(
        [&]() {
            if (original_sentence_utf8 == nullptr ||
                normalized_sentence_utf8 == nullptr ||
                source_path_utf8 == nullptr ||
                alphabetical_sort_key_utf8 == nullptr) {
                throw std::invalid_argument("sentence field is null");
            }
            engine_from(handle).add_sentence(
                sentence_id,
                original_sentence_utf8,
                normalized_sentence_utf8,
                source_path_utf8,
                offset,
                alphabetical_sort_key_utf8
            );
            return 1;
        },
        0
    );
}

int autocomplete_engine_load_corpus_directory(
    autocomplete_engine_handle handle,
    const char* directory_path_utf8
) {
    return protect(
        [&]() {
            if (directory_path_utf8 == nullptr) {
                throw std::invalid_argument("protobuf directory path is null");
            }
            engine_from(handle).load_corpus_directory(
                std::filesystem::u8path(directory_path_utf8)
            );
            return 1;
        },
        0
    );
}

int autocomplete_engine_save_index_cache(
    autocomplete_engine_handle handle,
    const char* cache_path_utf8,
    const char* corpus_fingerprint_utf8
) {
    return protect(
        [&]() {
            if (cache_path_utf8 == nullptr || corpus_fingerprint_utf8 == nullptr) {
                throw std::invalid_argument("native index cache argument is null");
            }
            engine_from(handle).save_index_cache(
                std::filesystem::u8path(cache_path_utf8),
                corpus_fingerprint_utf8
            );
            return 1;
        },
        0
    );
}

int autocomplete_engine_load_index_cache(
    autocomplete_engine_handle handle,
    const char* cache_path_utf8,
    const char* expected_fingerprint_utf8
) {
    return protect(
        [&]() {
            if (cache_path_utf8 == nullptr || expected_fingerprint_utf8 == nullptr) {
                throw std::invalid_argument("native index cache argument is null");
            }
            engine_from(handle).load_index_cache(
                std::filesystem::u8path(cache_path_utf8),
                expected_fingerprint_utf8
            );
            return 1;
        },
        0
    );
}

std::size_t autocomplete_engine_sentence_count(
    autocomplete_engine_handle handle
) {
    return protect(
        [&]() { return engine_from(handle).sentence_count(); },
        std::size_t{0}
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

const char* autocomplete_engine_sentence_original(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
) {
    return protect(
        [&]() { return engine_from(handle).sentence_by_id(sentence_id).original.c_str(); },
        static_cast<const char*>(nullptr)
    );
}

const char* autocomplete_engine_sentence_normalized(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
) {
    return protect(
        [&]() { return engine_from(handle).sentence_by_id(sentence_id).normalized.c_str(); },
        static_cast<const char*>(nullptr)
    );
}

const char* autocomplete_engine_sentence_source(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
) {
    return protect(
        [&]() { return engine_from(handle).sentence_by_id(sentence_id).source.c_str(); },
        static_cast<const char*>(nullptr)
    );
}

std::uint32_t autocomplete_engine_sentence_offset(
    autocomplete_engine_handle handle,
    std::uint32_t sentence_id
) {
    return protect(
        [&]() { return engine_from(handle).sentence_by_id(sentence_id).offset; },
        std::uint32_t{0}
    );
}

const char* autocomplete_engine_last_error() {
    return last_error.c_str();
}

}
