"""In-process logical version for the demo. This module never shells out or calls AWS."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulatorState:
    """Flag and logical version owned by the demo, not by a real deployment."""

    logical_version: dict[str, str] = field(default_factory=dict)

    def rollback(self, service: str, previous_version: str) -> dict[str, str]:
        self.logical_version[service] = previous_version
        return {
            "service": service,
            "logical_version": previous_version,
            "flag": "rolled_back",
        }
