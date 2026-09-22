locals {
  function_name              = "${var.project}-${var.environment}-incident-worker"
  bus_name                   = "${var.project}-${var.environment}-incidents"
  queue_name                 = "${var.project}-${var.environment}-incident-detected"
  dlq_name                   = "${var.project}-${var.environment}-incident-detected-dlq"
  detail_type                = "incident.detected.v1"
  visibility_timeout_seconds = var.lambda_timeout_seconds * 3
  quota_env = {
    AWS_REGION                       = var.aws_region
    AI_ENABLED                       = var.ai_enabled ? "true" : "false"
    AGENT_INVOCATION_ENABLED         = var.agent_invocation_enabled ? "true" : "false"
    RAG_ENABLED                      = var.rag_enabled ? "true" : "false"
    REMEDIATION_ENABLED              = var.remediation_enabled ? "true" : "false"
    TARGET_MONTHLY_COST_USD          = var.target_monthly_cost_usd
    MAX_INCIDENTS_PER_DAY            = tostring(var.max_incidents_per_day)
    MAX_AGENT_RUNS_PER_INCIDENT      = tostring(var.max_agent_runs_per_incident)
    MAX_AGENT_TURNS                  = tostring(var.max_agent_turns)
    MAX_TOOL_CALLS_PER_RUN           = tostring(var.max_tool_calls_per_run)
    MAX_RAG_CALLS_PER_RUN            = tostring(var.max_rag_calls_per_run)
    MAX_RAG_RESULTS                  = tostring(var.max_rag_results)
    MAX_LOG_WINDOW_MINUTES           = tostring(var.max_log_window_minutes)
    MAX_LOG_RESULTS                  = tostring(var.max_log_results)
    MAX_METRIC_WINDOW_MINUTES        = tostring(var.max_metric_window_minutes)
    MAX_SESSION_SECONDS              = tostring(var.max_session_seconds)
    MAX_MODEL_INPUT_TOKENS_PER_CALL  = tostring(var.max_model_input_tokens_per_call)
    MAX_MODEL_OUTPUT_TOKENS_PER_CALL = tostring(var.max_model_output_tokens_per_call)
    LOG_RETENTION_DAYS               = tostring(var.log_retention_days)
    EVAL_SAMPLE_RATE                 = var.eval_sample_rate
    INCIDENT_REPOSITORY              = "dynamodb"
    INCIDENTS_TABLE_NAME             = var.incidents_table_name
    DEPLOYMENTS_TABLE_NAME           = var.deployments_table_name
  }
}

data "archive_file" "worker" {
  type        = "zip"
  source_dir  = var.lambda_source_dir
  output_path = "${path.module}/build/incident-worker.zip"
}

resource "aws_cloudwatch_event_bus" "incidents" {
  name = local.bus_name
}

resource "aws_sqs_queue" "dlq" {
  name                      = local.dlq_name
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "detected" {
  name                       = local.queue_name
  visibility_timeout_seconds = local.visibility_timeout_seconds
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

data "aws_iam_policy_document" "queue" {
  statement {
    sid    = "AllowEventBridgeToQueue"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.detected.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.detected.arn]
    }
  }
}

data "aws_iam_policy_document" "dlq" {
  statement {
    sid    = "AllowEventBridgeToDlq"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.dlq.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.detected.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "detected" {
  queue_url = aws_sqs_queue.detected.id
  policy    = data.aws_iam_policy_document.queue.json
}

resource "aws_sqs_queue_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id
  policy    = data.aws_iam_policy_document.dlq.json
}

resource "aws_cloudwatch_event_rule" "detected" {
  name           = "${var.project}-${var.environment}-incident-detected"
  event_bus_name = aws_cloudwatch_event_bus.incidents.name
  description    = "Route versioned incident.detected.v1 events onto the ingest queue."

  event_pattern = jsonencode({
    source        = [var.event_source]
    "detail-type" = [local.detail_type]
  })
}

resource "aws_cloudwatch_event_target" "queue" {
  rule           = aws_cloudwatch_event_rule.detected.name
  event_bus_name = aws_cloudwatch_event_bus.incidents.name
  arn            = aws_sqs_queue.detected.arn

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = var.max_receive_count
  }

  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      aws_cloudwatch_log_group.worker.arn,
      "${aws_cloudwatch_log_group.worker.arn}:*",
    ]
  }

  statement {
    sid    = "IncidentsTable"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [var.incidents_table_arn]
  }

  statement {
    sid    = "ReadIngestQueue"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility",
    ]
    resources = [aws_sqs_queue.detected.arn]
  }
}

resource "aws_iam_role_policy" "investigation_worker" {
  name   = "investigation-worker-ingest"
  role   = var.investigation_worker_role_name
  policy = data.aws_iam_policy_document.worker.json
}

resource "aws_lambda_function" "worker" {
  function_name                  = local.function_name
  role                           = var.investigation_worker_role_arn
  handler                        = "incident_worker.handler.handler"
  runtime                        = "python3.12"
  filename                       = data.archive_file.worker.output_path
  source_code_hash               = data.archive_file.worker.output_base64sha256
  timeout                        = var.lambda_timeout_seconds
  memory_size                    = var.lambda_memory_mb
  reserved_concurrent_executions = var.reserved_concurrent_executions
  architectures                  = ["x86_64"]

  environment {
    variables = local.quota_env
  }

  depends_on = [
    aws_cloudwatch_log_group.worker,
    aws_iam_role_policy.investigation_worker,
  ]
}

resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn                   = aws_sqs_queue.detected.arn
  function_name                      = aws_lambda_function.worker.arn
  batch_size                         = 1
  enabled                            = true
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 0

  scaling_config {
    maximum_concurrency = var.lambda_maximum_concurrency
  }

  depends_on = [aws_iam_role_policy.investigation_worker]
}

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.project}-${var.environment}-dlq_messages"
  alarm_description   = "Observable dlq_messages metric: poison or exhausted ingest retries landed on the DLQ."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }
}
