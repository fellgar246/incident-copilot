locals {
  system_metrics = [
    "incidents_total",
    "incidents_by_status",
    "investigation_latency",
    "tool_error_rate",
  ]
  ai_metrics = [
    "llm_calls",
    "input_tokens",
    "output_tokens",
    "agent_turns",
    "tool_calls",
    "rag_calls",
    "confidence",
    "evaluation_score",
    "estimated_cost",
    "EstimatedCostPerIncident",
    "TokensPerIncident",
    "ToolCallsPerIncident",
    "RuntimePerIncident",
    "RagCallsPerIncident",
  ]
}

resource "aws_cloudwatch_dashboard" "agent" {
  dashboard_name = "${var.project}-${var.environment}-observability"

  dashboard_body = jsonencode({
    widgets = concat(
      [
        for index, name in local.system_metrics : {
          type   = "metric"
          x      = (index % 2) * 12
          y      = floor(index / 2) * 6
          width  = 12
          height = 6
          properties = {
            title  = name
            region = var.aws_region
            view   = "timeSeries"
            stat   = "Sum"
            period = 60
            metrics = [
              [var.metric_namespace, name],
            ]
          }
        }
      ],
      [
        {
          type   = "metric"
          x      = 0
          y      = 12
          width  = 12
          height = 6
          properties = {
            title   = "queue_age"
            region  = var.aws_region
            view    = "timeSeries"
            stat    = "Maximum"
            period  = 60
            metrics = [["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", var.ingest_queue_name]]
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 12
          width  = 12
          height = 6
          properties = {
            title   = "dlq_messages"
            region  = var.aws_region
            view    = "timeSeries"
            stat    = "Maximum"
            period  = 60
            metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.dlq_name]]
          }
        },
      ],
      [
        for index, name in local.ai_metrics : {
          type   = "metric"
          x      = (index % 2) * 12
          y      = 18 + floor(index / 2) * 6
          width  = 12
          height = 6
          properties = {
            title  = name
            region = var.aws_region
            view   = "timeSeries"
            stat   = "Sum"
            period = 60
            metrics = [
              [var.metric_namespace, name],
            ]
          }
        }
      ],
    )
  })
}
