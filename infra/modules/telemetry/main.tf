locals {
  log_group_arns = flatten([
    for group in aws_cloudwatch_log_group.demo : [
      group.arn,
      "${group.arn}:*",
    ]
  ])
}

resource "aws_cloudwatch_log_group" "demo" {
  for_each = toset(var.demo_services)

  name              = "/${var.project}/${var.environment}/${each.value}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_metric_filter" "error_rate" {
  for_each = aws_cloudwatch_log_group.demo

  name           = "${each.key}-error-rate"
  log_group_name = each.value.name
  pattern        = "{ $.level = \"ERROR\" }"

  metric_transformation {
    name      = "error_rate"
    namespace = var.metric_namespace
    value     = "1"
    unit      = "Count"

    dimensions = {
      Service = "$.service"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "request_count" {
  for_each = aws_cloudwatch_log_group.demo

  name           = "${each.key}-request-count"
  log_group_name = each.value.name
  pattern        = "{ $.service = \"*\" }"

  metric_transformation {
    name      = "request_count"
    namespace = var.metric_namespace
    value     = "1"
    unit      = "Count"

    dimensions = {
      Service = "$.service"
    }
  }
}

# GetMetricStatistics and ListMetrics do not support resource-level permissions.
# cloudwatch:namespace keeps those reads inside the demo custom-metric namespace.
data "aws_iam_policy_document" "cloudwatch_read" {
  statement {
    sid    = "ReadAllowlistedLogGroups"
    effect = "Allow"
    actions = [
      "logs:DescribeLogStreams",
      "logs:FilterLogEvents",
      "logs:GetLogEvents",
    ]
    resources = local.log_group_arns
  }

  statement {
    sid    = "ReadDemoMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = [var.metric_namespace]
    }
  }
}

resource "aws_iam_role_policy" "cloudwatch_read_tool" {
  name   = "cloudwatch-read-only"
  role   = var.cloudwatch_read_tool_role_name
  policy = data.aws_iam_policy_document.cloudwatch_read.json
}

resource "aws_iam_role_policy" "gateway_cloudwatch_read" {
  name   = "gateway-cloudwatch-read"
  role   = var.gateway_role_name
  policy = data.aws_iam_policy_document.cloudwatch_read.json
}
