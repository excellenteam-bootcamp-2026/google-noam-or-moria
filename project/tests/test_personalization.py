from __future__ import annotations

import json
from types import SimpleNamespace

from src.models import AutoCompleteData
from src.personalization import (
    GeminiCandidateReranker,
    GeminiJsonOrderModel,
    InMemorySearchHistoryStore,
    PersonalizedAutocomplete,
    SearchHistoryEntry,
    build_reranking_prompt,
    sanitize_candidate_order,
)


def candidates(count: int = 8) -> list[AutoCompleteData]:
    return [
        AutoCompleteData(f"Candidate {index}", "data.txt", index, 20 - index)
        for index in range(count)
    ]


class FixedOrderModel:
    def __init__(self, order):
        self.order = order
        self.prompts = []

    def rank(self, prompt, candidate_count):
        self.prompts.append((prompt, candidate_count))
        return self.order


def test_prompt_contains_no_user_id_or_source_paths() -> None:
    prompt = build_reranking_prompt(
        "python cache",
        [SearchHistoryEntry("protobuf", "Persistent cache design")],
        candidates(2),
    )

    assert "data.txt" not in prompt
    assert "user-123" not in prompt
    payload = json.loads(prompt.split("DATA:\n", 1)[1])
    assert payload["query"] == "python cache"
    assert [item["id"] for item in payload["candidates"]] == [0, 1]


def test_invalid_or_duplicate_model_ids_cannot_invent_results() -> None:
    assert sanitize_candidate_order([2, 2, 99, -1, "1", True, 0], 4) == [
        2,
        0,
        1,
        3,
    ]


def test_reranker_uses_history_and_preserves_candidate_objects() -> None:
    source = candidates()
    model = FixedOrderModel([4, 2, 0, 1, 3])
    reranker = GeminiCandidateReranker(model)

    results = reranker.rerank(
        "candidate",
        [SearchHistoryEntry("old", "Candidate 4")],
        source,
    )

    assert results == [source[4], source[2], source[0], source[1], source[3]]
    assert model.prompts[0][1] == len(source)


def test_empty_history_skips_the_model_call() -> None:
    model = FixedOrderModel([4, 3, 2, 1, 0])
    reranker = GeminiCandidateReranker(model)

    assert reranker.rerank("query", [], candidates()) == candidates()[:5]
    assert model.prompts == []


def test_personalized_search_falls_back_when_gemini_fails() -> None:
    class FailingModel:
        def rank(self, prompt, candidate_count):
            raise TimeoutError("Gemini timeout")

    source = candidates()
    requested_sizes = []

    def provider(query, size):
        requested_sizes.append((query, size))
        return source

    history = InMemorySearchHistoryStore()
    history.record("noam", SearchHistoryEntry("old", "Candidate 7"))
    service = PersonalizedAutocomplete(
        provider,
        history,
        GeminiCandidateReranker(FailingModel()),
    )

    assert service.complete("noam", "new") == source[:5]
    assert requested_sizes == [("new", 20)]


def test_google_adapter_requests_constrained_json() -> None:
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text='{"order":[1,0]}')

    client = SimpleNamespace(models=FakeModels())
    model = GeminiJsonOrderModel(client=client)

    assert model.rank("prompt", 2) == [1, 0]
    assert calls[0]["model"] == "gemini-2.5-flash-lite"
    assert calls[0]["config"]["response_mime_type"] == "application/json"
    assert calls[0]["config"]["response_json_schema"]["required"] == ["order"]
