"""Runtime settings for the ingest worker. Defaults keep local tests off AWS."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Settings:
    repository: str
    incidents_table_name: str
    deployments_table_name: str
    aws_region: str
    log_retention_days: int

    @property
    def use_dynamodb(self) -> bool:
        return self.repository == "dynamodb"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        repository=os.environ.get("INCIDENT_REPOSITORY", "memory").strip().lower(),
        incidents_table_name=os.environ.get(
            "INCIDENTS_TABLE_NAME", "ai-incident-copilot-dev-incidents"
        ),
        deployments_table_name=os.environ.get(
            "DEPLOYMENTS_TABLE_NAME", "ai-incident-copilot-dev-deployments"
        ),
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        log_retention_days=int(os.environ.get("LOG_RETENTION_DAYS", "7")),
    )


def reset_settings_cache() -> None:
    get_settings.cache_clear()
