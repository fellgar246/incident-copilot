"""Actor identifiers on domain events: system, agent, or human:{id}."""

from __future__ import annotations

from incident_contracts.enums import ActorKind
from incident_contracts.errors import InvalidActorError

_HUMAN_PREFIX = "human:"


def format_actor(kind: ActorKind, human_id: str | None = None) -> str:
    if kind is ActorKind.HUMAN:
        if not human_id:
            raise InvalidActorError("human actor requires human_id")
        return f"{_HUMAN_PREFIX}{human_id}"
    return kind.value


def parse_actor(actor: str) -> tuple[ActorKind, str | None]:
    if actor == ActorKind.SYSTEM.value:
        return ActorKind.SYSTEM, None
    if actor == ActorKind.AGENT.value:
        return ActorKind.AGENT, None
    if actor.startswith(_HUMAN_PREFIX):
        human_id = actor.removeprefix(_HUMAN_PREFIX)
        if human_id and human_id.strip() == human_id and " " not in human_id:
            return ActorKind.HUMAN, human_id
    raise InvalidActorError(f"actor must be 'system', 'agent', or 'human:{{id}}'; got {actor!r}")


def validate_actor(actor: str) -> str:
    parse_actor(actor)
    return actor
