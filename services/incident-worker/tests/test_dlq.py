from __future__ import annotations

import json
from typing import Any

import boto3
import pytest
from incident_contracts.enums import ScenarioId
from incident_contracts.events import detected_event_from_fixture
from incident_worker.envelope import unwrap_sqs_body
from incident_worker.handler import handle_records
from incident_worker.store import build_repository
from moto import mock_aws

from simulator import simulate

pytestmark = pytest.mark.integration

REGION = "us-east-1"
INCIDENTS = "test-incidents"
DEPLOYMENTS = "test-deployments"


def _create_tables(client: Any) -> None:
    for name in (INCIDENTS, DEPLOYMENTS):
        client.create_table(
            TableName=name,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )


def _payload() -> dict[str, Any]:
    fixture = simulate(ScenarioId.QUEUE_BACKLOG, seed="ddb-ingest")
    return detected_event_from_fixture(fixture).model_dump(mode="json")


def _sqs_record(queue_url: str, body: dict[str, Any], sqs: Any) -> dict[str, Any]:
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    received = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, VisibilityTimeout=0)
    message = received["Messages"][0]
    return {
        "Records": [
            {
                "messageId": message["MessageId"],
                "receiptHandle": message["ReceiptHandle"],
                "body": message["Body"],
                "attributes": message.get("Attributes", {}),
                "eventSource": "aws:sqs",
            }
        ]
    }


@mock_aws
def test_event_to_incident_via_dynamodb(monkeypatch: Any) -> None:
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("INCIDENT_REPOSITORY", "dynamodb")
    monkeypatch.setenv("INCIDENTS_TABLE_NAME", INCIDENTS)
    monkeypatch.setenv("DEPLOYMENTS_TABLE_NAME", DEPLOYMENTS)
    monkeypatch.setenv("LOG_RETENTION_DAYS", "7")
    from incident_worker.settings import reset_settings_cache

    reset_settings_cache()
    client = boto3.client("dynamodb", region_name=REGION)
    _create_tables(client)
    repository = build_repository()
    payload = _payload()
    result = handle_records(
        {"Records": [{"messageId": "m1", "body": json.dumps(payload)}]},
        repository=repository,
    )
    replay = handle_records(
        {"Records": [{"messageId": "m2", "body": json.dumps(payload)}]},
        repository=repository,
    )
    assert result == replay == {"batchItemFailures": []}
    incidents = repository.list_incidents()
    assert len(incidents) == 1
    assert incidents[0].correlation_id == payload["correlation_id"]
    assert incidents[0].source_event_id == payload["event_id"]
    reset_settings_cache()


@mock_aws
def test_poison_message_is_redriven_to_dlq() -> None:
    sqs = boto3.client("sqs", region_name=REGION)
    dlq = sqs.create_queue(QueueName="incident-detected-dlq")
    dlq_url = dlq["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    queue = sqs.create_queue(
        QueueName="incident-detected",
        Attributes={
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"})
        },
    )
    queue_url = queue["QueueUrl"]
    poison = {
        "schema_version": "9",
        "event_id": "evt_poison",
        "alarm_name": "payments-5xx-rate",
        "service": "payments-api",
        "severity": "HIGH",
        "occurred_at": "2026-09-20T14:00:00.000Z",
        "correlation_id": "cor_poison",
        "scenario": "deployment_regression",
    }
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(poison))

    from incident_contracts.repository import InMemoryIncidentRepository

    repository = InMemoryIncidentRepository()
    for _ in range(3):
        received = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            VisibilityTimeout=30,
            AttributeNames=["All"],
        )
        messages = received.get("Messages") or []
        if not messages:
            break
        record = {
            "Records": [
                {
                    "messageId": messages[0]["MessageId"],
                    "receiptHandle": messages[0]["ReceiptHandle"],
                    "body": messages[0]["Body"],
                    "eventSource": "aws:sqs",
                }
            ]
        }
        result = handle_records(record, repository=repository)
        assert result["batchItemFailures"]
        assert unwrap_sqs_body(messages[0]["Body"])["schema_version"] == "9"
        sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=messages[0]["ReceiptHandle"],
            VisibilityTimeout=0,
        )

    source_left = (
        sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1).get("Messages") or []
    )
    dlq_messages = (
        sqs.receive_message(QueueUrl=dlq_url, MaxNumberOfMessages=1).get("Messages") or []
    )
    assert not source_left
    assert dlq_messages
    assert json.loads(dlq_messages[0]["Body"])["event_id"] == "evt_poison"
    assert repository.list_incidents() == []
