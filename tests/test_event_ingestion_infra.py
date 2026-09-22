from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVENTS_MAIN = REPO_ROOT / "infra" / "modules" / "events" / "main.tf"
IAM_MAIN = REPO_ROOT / "infra" / "modules" / "iam" / "main.tf"
DEV_MAIN = REPO_ROOT / "infra" / "environments" / "dev" / "main.tf"


def test_events_module_wires_bus_queue_dlq_and_bounded_retry() -> None:
    source = EVENTS_MAIN.read_text(encoding="utf-8")
    assert "aws_cloudwatch_event_bus" in source
    assert "incident.detected.v1" in source
    assert "aws_sqs_queue" in source
    assert "deadLetterTargetArn" in source
    assert "maxReceiveCount" in source
    assert "aws_lambda_event_source_mapping" in source
    assert "ReportBatchItemFailures" in source
    assert "incident_worker.handler.handler" in source
    assert "maximum_retry_attempts" in source
    alarm = source[source.index("aws_cloudwatch_metric_alarm") :]
    assert "dlq_messages" in alarm
    assert "ApproximateNumberOfMessagesVisible" in alarm


def test_investigation_worker_role_exists_and_is_wired() -> None:
    iam = IAM_MAIN.read_text(encoding="utf-8")
    assert "aws_iam_role" in iam
    assert "investigation-worker" in iam
    assert "lambda.amazonaws.com" in iam
    dev = DEV_MAIN.read_text(encoding="utf-8")
    assert 'source = "../../modules/events"' in dev
    assert "investigation_worker_role_arn" in dev
    assert "event_bus_name" in dev
