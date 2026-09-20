"""Build deterministic IncidentFixture objects for the four demo scenarios."""

from __future__ import annotations

from datetime import UTC, datetime

from incident_contracts.enums import (
    ActorKind,
    EventType,
    EvidenceKind,
    IncidentStatus,
    ScenarioId,
)
from incident_contracts.models import (
    Deployment,
    Diagnosis,
    Evidence,
    Incident,
    IncidentEvent,
    IncidentFixture,
    LogSample,
    MetricSample,
    TelemetryBundle,
)

from simulator.catalog import SPECS, at
from simulator.ids import seeded_id

DEFAULT_SEED = "golden"
ORIGIN = datetime(2026, 9, 20, 14, 0, 0, tzinfo=UTC)


def simulate(scenario: ScenarioId | str, seed: str | None = None) -> IncidentFixture:
    """Return the fixture for `scenario`. Identical seed ⇒ identical fixture."""
    scenario_id = ScenarioId(scenario)
    resolved_seed = seed or DEFAULT_SEED
    spec = SPECS[scenario_id]
    origin = ORIGIN
    incident_id = seeded_id("inc", resolved_seed, f"{scenario_id}:incident")
    event_id = seeded_id("evt", resolved_seed, f"{scenario_id}:alarm")
    correlation_id = seeded_id("cor", resolved_seed, f"{scenario_id}:correlation")
    simulation_id = seeded_id("sim", resolved_seed, f"{scenario_id}:simulation")

    evidence = _evidence(scenario_id, resolved_seed, spec.service, origin)
    deployments = _deployments(scenario_id, spec.service, origin)
    telemetry = _telemetry(scenario_id, spec.service, origin)
    diagnosis = _diagnosis(scenario_id, evidence)

    incident = Incident(
        incident_id=incident_id,
        service=spec.service,
        severity=spec.severity,
        status=IncidentStatus.DETECTED,
        alarm_name=spec.alarm_name,
        started_at=origin,
        updated_at=origin,
        correlation_id=correlation_id,
        simulation_id=simulation_id,
        source_event_id=event_id,
    )
    alarm_event = IncidentEvent(
        event_id=event_id,
        incident_id=incident_id,
        event_type=EventType.ALARM_RECEIVED,
        timestamp=origin,
        actor=ActorKind.SYSTEM.value,
        payload={
            "alarm_name": spec.alarm_name,
            "scenario": scenario_id.value,
            "schema_version": "1",
        },
        from_status=None,
        to_status=IncidentStatus.DETECTED,
    )
    evidence_events = [
        IncidentEvent(
            event_id=seeded_id("evt", resolved_seed, f"{scenario_id}:evidence:{item.evidence_id}"),
            incident_id=incident_id,
            event_type=EventType.EVIDENCE_ADDED,
            timestamp=item.observed_at,
            actor=ActorKind.SYSTEM.value,
            payload={"evidence_id": item.evidence_id, "kind": item.kind.value},
            from_status=IncidentStatus.DETECTED,
            to_status=IncidentStatus.DETECTED,
        )
        for item in evidence
    ]
    return IncidentFixture(
        scenario=scenario_id,
        seed=resolved_seed,
        incident=incident,
        events=[alarm_event, *evidence_events],
        evidence=evidence,
        deployments=deployments,
        expected_diagnosis=diagnosis,
        telemetry=telemetry,
    )


def _evidence(
    scenario: ScenarioId, seed: str, service: str, origin: datetime
) -> list[Evidence]:
    def eid(name: str) -> str:
        return seeded_id("evd", seed, f"{scenario}:{name}")

    if scenario is ScenarioId.DEPLOYMENT_REGRESSION:
        return [
            Evidence(
                evidence_id=eid("5xx"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.metrics",
                summary="HTTP 5xx rate increased immediately after the latest payments-api deploy.",
                observed_at=at(origin, 2),
                payload={"metric": "5xx_rate", "before": 0.2, "after": 8.4, "unit": "Percent"},
            ),
            Evidence(
                evidence_id=eid("p95"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.metrics",
                summary="Latency p95 rose from 180ms to 2100ms in the same window.",
                observed_at=at(origin, 2, 15),
                payload={"metric": "latency_p95", "before_ms": 180, "after_ms": 2100},
            ),
            Evidence(
                evidence_id=eid("timeout"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.logs",
                summary="Error logs show repeated UPSTREAM_TIMEOUT from the payments client.",
                observed_at=at(origin, 3),
                payload={"error_code": "UPSTREAM_TIMEOUT", "count": 47},
            ),
            Evidence(
                evidence_id=eid("deploy"),
                kind=EvidenceKind.OBSERVED,
                source="deployments",
                summary="Version 2026.09.20.3 shipped 18 minutes before the alarm.",
                observed_at=at(origin, -18),
                payload={"version": "2026.09.20.3", "commit_sha": "a1b2c3d4e5f6"},
            ),
            Evidence(
                evidence_id=eid("runbook"),
                kind=EvidenceKind.RETRIEVED,
                source="knowledge.runbooks",
                summary="Runbook rb_payments_5xx_after_deploy recommends a simulated rollback.",
                observed_at=at(origin, 4),
                payload={"document_id": "rb_payments_5xx_after_deploy", "version": 3},
            ),
        ]
    if scenario is ScenarioId.CONNECTION_POOL_EXHAUSTION:
        return [
            Evidence(
                evidence_id=eid("latency"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.metrics",
                summary="orders-api latency is elevated while CPU remains well below saturation.",
                observed_at=at(origin, 1),
                payload={"latency_p95_ms": 1600, "cpu_percent": 22},
            ),
            Evidence(
                evidence_id=eid("pool"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.logs",
                summary="Logs contain POOL_EXHAUSTED; checked-out connections sit at 98/100.",
                observed_at=at(origin, 1, 30),
                payload={"error_code": "POOL_EXHAUSTED", "checked_out": 98, "max": 100},
            ),
            Evidence(
                evidence_id=eid("runbook"),
                kind=EvidenceKind.RETRIEVED,
                source="knowledge.runbooks",
                summary="Runbook rb_orders_pool_exhaustion distinguishes pool saturation from CPU.",
                observed_at=at(origin, 3),
                payload={"document_id": "rb_orders_pool_exhaustion"},
            ),
        ]
    if scenario is ScenarioId.QUEUE_BACKLOG:
        return [
            Evidence(
                evidence_id=eid("visible"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.metrics",
                summary="Visible SQS messages grew from 12 to 840 in 20 minutes.",
                observed_at=at(origin, 1),
                payload={
                    "metric": "ApproximateNumberOfMessagesVisible",
                    "before": 12,
                    "after": 840,
                },
            ),
            Evidence(
                evidence_id=eid("age"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.metrics",
                summary="Age of oldest message exceeded 15 minutes.",
                observed_at=at(origin, 1, 20),
                payload={"metric": "ApproximateAgeOfOldestMessage", "seconds": 960},
            ),
            Evidence(
                evidence_id=eid("duration"),
                kind=EvidenceKind.OBSERVED,
                source="cloudwatch.metrics",
                summary="Worker duration p95 doubled, pointing at a consumer bottleneck.",
                observed_at=at(origin, 2),
                payload={"metric": "worker_duration_p95_ms", "value": 4200},
            ),
            Evidence(
                evidence_id=eid("runbook"),
                kind=EvidenceKind.RETRIEVED,
                source="knowledge.runbooks",
                summary=(
                    "Runbook rb_notifications_sqs_backlog suggests a safe concurrency bump in demo."
                ),
                observed_at=at(origin, 3),
                payload={"document_id": "rb_notifications_sqs_backlog"},
            ),
        ]
    return [
        Evidence(
            evidence_id=eid("cpu"),
            kind=EvidenceKind.OBSERVED,
            source="cloudwatch.metrics",
            summary="CPU spiked for 90 seconds then returned to baseline; error rate unchanged.",
            observed_at=at(origin, 1),
            payload={"cpu_percent_peak": 71, "5xx_rate": 0.1, "duration_seconds": 90},
        ),
        Evidence(
            evidence_id=eid("logs"),
            kind=EvidenceKind.OBSERVED,
            source="cloudwatch.logs",
            summary="No matching error burst; recent INFO logs only.",
            observed_at=at(origin, 2),
            payload={"error_count": 0, "info_count": 24},
        ),
        Evidence(
            evidence_id=eid("contradiction"),
            kind=EvidenceKind.INFERENCE,
            source="agent.hypothesis",
            summary="Latency and 5xx contradict a genuine outage; more evidence is required.",
            observed_at=at(origin, 3),
            payload={"confidence_cap": 0.35},
        ),
    ]


def _deployments(scenario: ScenarioId, service: str, origin: datetime) -> list[Deployment]:
    if scenario is ScenarioId.DEPLOYMENT_REGRESSION:
        return [
            Deployment(
                service=service,
                version="2026.09.20.3",
                commit_sha="a1b2c3d4e5f67890abcd",
                deployed_at=at(origin, -18),
                change_summary="Changed timeout and retry policy",
            ),
            Deployment(
                service=service,
                version="2026.09.20.2",
                commit_sha="0099aabbccddeeff0011",
                deployed_at=at(origin, -180),
                change_summary="Baseline release",
            ),
        ]
    if scenario is ScenarioId.CONNECTION_POOL_EXHAUSTION:
        return [
            Deployment(
                service=service,
                version="2026.09.18.1",
                commit_sha="feedfacecafebeef1234",
                deployed_at=at(origin, -2880),
                change_summary="Unrelated schema comment change",
            )
        ]
    if scenario is ScenarioId.QUEUE_BACKLOG:
        return [
            Deployment(
                service=service,
                version="2026.09.19.4",
                commit_sha="c0ffeeabc123def45678",
                deployed_at=at(origin, -720),
                change_summary="Worker batch size left at 1",
            )
        ]
    return [
        Deployment(
            service=service,
            version="2026.09.20.2",
            commit_sha="0099aabbccddeeff0011",
            deployed_at=at(origin, -180),
            change_summary="Baseline release, no overlap with the brief CPU blip",
        )
    ]


def _telemetry(scenario: ScenarioId, service: str, origin: datetime) -> TelemetryBundle:
    if scenario is ScenarioId.DEPLOYMENT_REGRESSION:
        logs = [
            LogSample(
                timestamp=at(origin, 1, 5),
                service=service,
                level="ERROR",
                message="UPSTREAM_TIMEOUT calling billing-api",
                fields={"error_code": "UPSTREAM_TIMEOUT", "upstream": "billing-api"},
            ),
            LogSample(
                timestamp=at(origin, 1, 20),
                service=service,
                level="ERROR",
                message="UPSTREAM_TIMEOUT calling billing-api",
                fields={"error_code": "UPSTREAM_TIMEOUT", "upstream": "billing-api"},
            ),
        ]
        metrics = [
            MetricSample(
                timestamp=origin, service=service, name="5xx_rate", value=8.4, unit="Percent"
            ),
            MetricSample(
                timestamp=origin,
                service=service,
                name="latency_p95",
                value=2100,
                unit="Milliseconds",
            ),
        ]
        return TelemetryBundle(logs=logs, metrics=metrics)
    if scenario is ScenarioId.CONNECTION_POOL_EXHAUSTION:
        return TelemetryBundle(
            logs=[
                LogSample(
                    timestamp=at(origin, 1, 10),
                    service=service,
                    level="ERROR",
                    message="POOL_EXHAUSTED waiting for checkout",
                    fields={"error_code": "POOL_EXHAUSTED", "checked_out": 98, "max": 100},
                )
            ],
            metrics=[
                MetricSample(
                    timestamp=origin,
                    service=service,
                    name="latency_p95",
                    value=1600,
                    unit="Milliseconds",
                ),
                MetricSample(
                    timestamp=origin, service=service, name="cpu_percent", value=22, unit="Percent"
                ),
                MetricSample(
                    timestamp=origin, service=service, name="db_connections", value=98, unit="Count"
                ),
            ],
        )
    if scenario is ScenarioId.QUEUE_BACKLOG:
        return TelemetryBundle(
            logs=[
                LogSample(
                    timestamp=at(origin, 2),
                    service=service,
                    level="WARN",
                    message="processing lag increasing",
                    fields={"queue": "notifications", "visible": 840},
                )
            ],
            metrics=[
                MetricSample(
                    timestamp=origin,
                    service=service,
                    name="ApproximateNumberOfMessagesVisible",
                    value=840,
                ),
                MetricSample(
                    timestamp=origin,
                    service=service,
                    name="ApproximateAgeOfOldestMessage",
                    value=960,
                    unit="Seconds",
                ),
                MetricSample(
                    timestamp=origin,
                    service=service,
                    name="worker_duration_p95",
                    value=4200,
                    unit="Milliseconds",
                ),
            ],
        )
    return TelemetryBundle(
        logs=[
            LogSample(
                timestamp=at(origin, 1),
                service=service,
                level="INFO",
                message="gc pause recovered",
                fields={"duration_ms": 40},
            )
        ],
        metrics=[
            MetricSample(
                timestamp=origin, service=service, name="cpu_percent", value=71, unit="Percent"
            ),
            MetricSample(
                timestamp=at(origin, 2),
                service=service,
                name="cpu_percent",
                value=18,
                unit="Percent",
            ),
            MetricSample(
                timestamp=origin, service=service, name="5xx_rate", value=0.1, unit="Percent"
            ),
        ],
    )


def _diagnosis(scenario: ScenarioId, evidence: list[Evidence]) -> Diagnosis:
    if scenario is ScenarioId.DEPLOYMENT_REGRESSION:
        return Diagnosis(
            summary="5xx and latency rose in lockstep with payments-api 2026.09.20.3.",
            probable_cause="Deployment regression: timeout/retry change causing UPSTREAM_TIMEOUT.",
            confidence=0.91,
            evidence=evidence,
            retrieved_sources=["rb_payments_5xx_after_deploy"],
            alternative_hypotheses=["Regional dependency outage"],
            recommended_action="Simulated rollback of payments-api to 2026.09.20.2",
            requires_approval=True,
            destructive=False,
        )
    if scenario is ScenarioId.CONNECTION_POOL_EXHAUSTION:
        return Diagnosis(
            summary="Latency is explained by a saturated connection pool, not CPU.",
            probable_cause="Connection pool exhaustion (POOL_EXHAUSTED at 98/100).",
            confidence=0.88,
            evidence=evidence,
            retrieved_sources=["rb_orders_pool_exhaustion"],
            alternative_hypotheses=["CPU saturation", "Garbage collection storm"],
            recommended_action="Raise demo pool size by 1 (SAFE_WRITE) after approval",
            requires_approval=True,
            destructive=False,
        )
    if scenario is ScenarioId.QUEUE_BACKLOG:
        return Diagnosis(
            summary="Queue depth and oldest-message age show a consumer bottleneck.",
            probable_cause="notifications-worker cannot keep up with enqueue rate.",
            confidence=0.86,
            evidence=evidence,
            retrieved_sources=["rb_notifications_sqs_backlog"],
            alternative_hypotheses=["Producer retry storm"],
            recommended_action="Increase demo worker concurrency by 1 after approval",
            requires_approval=True,
            destructive=False,
        )
    return Diagnosis(
        summary="Symptoms are brief and contradictory; there is not enough evidence for a fix.",
        probable_cause="Likely false positive from a transient CPU blip.",
        confidence=0.28,
        evidence=evidence,
        retrieved_sources=[],
        alternative_hypotheses=["Hidden error burst not yet in the log window"],
        recommended_action="Collect more evidence; do not remediate",
        requires_approval=False,
        destructive=False,
    )
