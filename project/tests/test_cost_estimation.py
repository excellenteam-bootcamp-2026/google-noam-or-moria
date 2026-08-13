import pytest

from src.cost_estimation import TokenPricing, estimate_token_cost


def test_estimates_one_million_flash_lite_requests() -> None:
    estimate = estimate_token_cost(
        requests=1_000_000,
        input_tokens_per_request=300,
        output_tokens_per_request=50,
        pricing=TokenPricing(0.10, 0.40),
    )

    assert estimate.input_cost == pytest.approx(30.0)
    assert estimate.output_cost == pytest.approx(20.0)
    assert estimate.total_cost == pytest.approx(50.0)


def test_five_percent_gemini_cascade_reduces_token_cost_proportionally() -> None:
    estimate = estimate_token_cost(
        requests=50_000,
        input_tokens_per_request=300,
        output_tokens_per_request=50,
        pricing=TokenPricing(0.10, 0.40),
    )

    assert estimate.total_cost == pytest.approx(2.5)


def test_rejects_negative_assumptions() -> None:
    with pytest.raises(ValueError):
        estimate_token_cost(-1, 300, 50, TokenPricing(0.10, 0.40))
