output "event_bus_name" {
  description = "Name of the incident event bus."
  value       = aws_cloudwatch_event_bus.incidents.name
}

output "event_bus_arn" {
  description = "ARN of the incident event bus."
  value       = aws_cloudwatch_event_bus.incidents.arn
}

output "event_source" {
  description = "EventBridge source used for incident.detected.v1."
  value       = var.event_source
}

output "queue_name" {
  description = "Name of the ingest SQS queue."
  value       = aws_sqs_queue.detected.name
}

output "dlq_name" {
  description = "Name of the ingest DLQ."
  value       = aws_sqs_queue.dlq.name
}

output "queue_url" {
  description = "URL of the ingest SQS queue."
  value       = aws_sqs_queue.detected.url
}

output "queue_arn" {
  description = "ARN of the ingest SQS queue."
  value       = aws_sqs_queue.detected.arn
}

output "dlq_url" {
  description = "URL of the ingest DLQ."
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "ARN of the ingest DLQ."
  value       = aws_sqs_queue.dlq.arn
}

output "worker_function_name" {
  description = "Name of the incident-worker Lambda."
  value       = aws_lambda_function.worker.function_name
}

output "dlq_messages_alarm_name" {
  description = "CloudWatch alarm that exposes the dlq_messages signal."
  value       = aws_cloudwatch_metric_alarm.dlq_messages.alarm_name
}
