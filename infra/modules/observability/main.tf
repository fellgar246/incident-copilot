resource "aws_cloudwatch_log_group" "traces" {
  name              = "/${var.project}/${var.environment}/traces"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "metrics" {
  name              = "/${var.project}/${var.environment}/metrics"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "put_metrics" {
  statement {
    sid       = "PutObservabilityMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = [var.metric_namespace]
    }
  }
}

resource "aws_iam_role_policy" "api_metrics" {
  name   = "observability-metrics"
  role   = var.api_role_name
  policy = data.aws_iam_policy_document.put_metrics.json
}

resource "aws_iam_role_policy" "worker_metrics" {
  name   = "observability-metrics"
  role   = var.worker_role_name
  policy = data.aws_iam_policy_document.put_metrics.json
}
