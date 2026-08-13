"""Small, explicit Stage C token-cost calculator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPricing:
    """USD price per one million input and output tokens."""

    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class CostEstimate:
    input_cost: float
    output_cost: float

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


def estimate_token_cost(
    requests: int,
    input_tokens_per_request: int,
    output_tokens_per_request: int,
    pricing: TokenPricing,
) -> CostEstimate:
    """Estimate API token cost while rejecting impossible assumptions."""

    values = (requests, input_tokens_per_request, output_tokens_per_request)
    if any(value < 0 for value in values):
        raise ValueError("request and token counts cannot be negative")
    if pricing.input_per_million < 0 or pricing.output_per_million < 0:
        raise ValueError("token prices cannot be negative")

    input_tokens = requests * input_tokens_per_request
    output_tokens = requests * output_tokens_per_request
    return CostEstimate(
        input_cost=input_tokens / 1_000_000 * pricing.input_per_million,
        output_cost=output_tokens / 1_000_000 * pricing.output_per_million,
    )
