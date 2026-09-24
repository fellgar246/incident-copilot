from __future__ import annotations

import pytest
from cost_guardrails.estimator import estimate_cost_usd


def test_nova_micro_price() -> None:
    estimate = estimate_cost_usd("us.amazon.nova-micro-v1:0", 1_000_000, 1_000_000)
    assert estimate.estimated_cost_usd == pytest.approx(0.175)


def test_unknown_model_uses_default_rate() -> None:
    estimate = estimate_cost_usd("custom-model", 0, 0)
    assert estimate.estimated_cost_usd == 0.0
    assert estimate.model == "custom-model"


def test_negative_tokens_rejected() -> None:
    with pytest.raises(ValueError):
        estimate_cost_usd("us.amazon.nova-micro-v1:0", -1, 0)
