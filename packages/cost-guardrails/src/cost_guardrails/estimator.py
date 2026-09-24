"""Estimate model spend from token counts. Figures are list prices, not an invoice."""

from __future__ import annotations

from dataclasses import dataclass

# USD per 1,000,000 tokens. Unknown models use the default row.
_DEFAULT_MODEL = "default"
_PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "us.amazon.nova-micro-v1:0": (0.035, 0.14),
    "amazon.nova-micro-v1:0": (0.035, 0.14),
    "us.amazon.nova-lite-v1:0": (0.06, 0.24),
    "amazon.nova-lite-v1:0": (0.06, 0.24),
    _DEFAULT_MODEL: (0.25, 1.25),
}


@dataclass(frozen=True, slots=True)
class CostEstimate:
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> CostEstimate:
    """Return a non-negative estimate for one run's token totals."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be >= 0")
    input_rate, output_rate = _PRICES_PER_MILLION.get(model, _PRICES_PER_MILLION[_DEFAULT_MODEL])
    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    return CostEstimate(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=round(cost, 8),
    )
