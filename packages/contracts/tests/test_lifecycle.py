from __future__ import annotations

from datetime import UTC, datetime

import pytest
from incident_contracts.actors import format_actor, parse_actor
from incident_contracts.enums import ActorKind, IncidentStatus
from incident_contracts.errors import IllegalTransitionError, InvalidActorError
from incident_contracts.lifecycle import ALLOWED_TRANSITIONS, transition
from incident_contracts.models import Incident, Severity

NOW = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)


def _incident(status: IncidentStatus = IncidentStatus.DETECTED) -> Incident:
    return Incident(
        incident_id="inc_test",
        service="payments-api",
        severity=Severity.HIGH,
        status=status,
        alarm_name="payments-5xx-rate",
        started_at=NOW,
        updated_at=NOW,
        correlation_id="cor_test",
    )


def test_every_status_has_an_explicit_transition_row() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(IncidentStatus)


def test_legal_transition_updates_status_and_emits_event() -> None:
    updated, event = transition(
        _incident(),
        IncidentStatus.QUEUED,
        actor=ActorKind.SYSTEM.value,
        at=NOW,
        event_id="evt_1",
    )
    assert updated.status is IncidentStatus.QUEUED
    assert event.from_status is IncidentStatus.DETECTED
    assert event.to_status is IncidentStatus.QUEUED
    assert event.actor == "system"


def test_illegal_transition_is_rejected() -> None:
    with pytest.raises(IllegalTransitionError, match="DETECTED -> RESOLVED"):
        transition(
            _incident(),
            IncidentStatus.RESOLVED,
            actor=ActorKind.SYSTEM.value,
            at=NOW,
            event_id="evt_bad",
        )


def test_terminal_states_have_no_outbound_edges() -> None:
    for status in (IncidentStatus.REJECTED, IncidentStatus.FAILED, IncidentStatus.RESOLVED):
        assert ALLOWED_TRANSITIONS[status] == frozenset()


def test_human_actor_is_prefixed() -> None:
    updated, event = transition(
        _incident(),
        IncidentStatus.QUEUED,
        actor=format_actor(ActorKind.HUMAN, "ada"),
        at=NOW,
        event_id="evt_human",
    )
    assert updated.status is IncidentStatus.QUEUED
    assert event.actor == "human:ada"
    assert event.timestamp == NOW
    assert parse_actor(event.actor) == (ActorKind.HUMAN, "ada")


def test_unknown_actor_is_rejected() -> None:
    with pytest.raises(InvalidActorError, match="system"):
        transition(
            _incident(),
            IncidentStatus.QUEUED,
            actor="bot",
            at=NOW,
            event_id="evt_bot",
        )


def test_empty_human_actor_is_rejected() -> None:
    with pytest.raises(InvalidActorError):
        format_actor(ActorKind.HUMAN, None)
    with pytest.raises(InvalidActorError):
        parse_actor("human:")
    with pytest.raises(InvalidActorError):
        parse_actor("human: ada")
