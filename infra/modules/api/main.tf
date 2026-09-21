locals {
  function_name = "${var.project}-${var.environment}-api"
  role_name     = "${var.project}-${var.environment}-api"
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
    CORS_ORIGINS                     = var.cors_origins
  }
}

data "archive_file" "api" {
  type        = "zip"
  source_dir  = var.lambda_source_dir
  output_path = "${path.module}/build/api.zip"
}

data "aws_iam_policy_document" "api_assume" {
  statement {
    sid     = "LambdaAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.api_assume.json
  description        = "Least-privilege execution role for the incident API Lambda."
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "api" {
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      aws_cloudwatch_log_group.api.arn,
      "${aws_cloudwatch_log_group.api.arn}:*",
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
    resources = [
      var.incidents_table_arn,
      var.deployments_table_arn,
    ]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "api-least-privilege"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_lambda_function" "api" {
  function_name                  = local.function_name
  role                           = aws_iam_role.api.arn
  handler                        = "api.handler.handler"
  runtime                        = "python3.12"
  filename                       = data.archive_file.api.output_path
  source_code_hash               = data.archive_file.api.output_base64sha256
  timeout                        = var.lambda_timeout_seconds
  memory_size                    = var.lambda_memory_mb
  reserved_concurrent_executions = var.reserved_concurrent_executions
  architectures                  = ["x86_64"]

  environment {
    variables = local.quota_env
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project}-${var.environment}-http"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = var.lambda_timeout_seconds * 1000
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
