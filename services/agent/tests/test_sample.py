from __future__ import annotations

from agent.sample import should_sample


def test_sample_rate_is_stable() -> None:
    assert should_sample("inc_a", 0.0) is False
    assert should_sample("inc_a", 1.0) is True
    assert should_sample("inc_a", 0.10) is should_sample("inc_a", 0.10)
