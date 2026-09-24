data "aws_iam_policy_document" "github_oidc_assume" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    sid     = "GitHubActionsAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_oidc ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = var.github_oidc_thumbprints

  lifecycle {
    precondition {
      condition     = length(var.github_org) > 0 && var.github_org != "YOUR_GITHUB_ORG"
      error_message = "github_org must be set to a real GitHub org or user when enable_github_oidc is true."
    }
  }
}

resource "aws_iam_role" "ci_deploy" {
  count              = var.enable_github_oidc ? 1 : 0
  name               = "${var.project}-${var.environment}-ci-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_assume[0].json
  description        = "Skeleton CI role assumed by GitHub Actions via OIDC. Deploy permissions are added later."
}

# Skeleton only: identity check. Deploy permissions are added later.
# sts:GetCallerIdentity does not support resource-level IAM, so Resource=* is required.
data "aws_iam_policy_document" "ci_deploy_skeleton" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    sid       = "CallerIdentity"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ci_deploy_skeleton" {
  count  = var.enable_github_oidc ? 1 : 0
  name   = "sts-caller-identity"
  role   = aws_iam_role.ci_deploy[0].id
  policy = data.aws_iam_policy_document.ci_deploy_skeleton[0].json
}

data "aws_iam_policy_document" "lambda_assume" {
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

resource "aws_iam_role" "investigation_worker" {
  name               = "${var.project}-${var.environment}-investigation-worker"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  description        = "investigation-worker-role: DynamoDB writes and SQS reads for incident ingest."
}

data "aws_iam_policy_document" "agentcore_runtime_assume" {
  statement {
    sid     = "AgentCoreRuntimeAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agentcore_runtime" {
  name               = "${var.project}-${var.environment}-agentcore-runtime"
  assume_role_policy = data.aws_iam_policy_document.agentcore_runtime_assume.json
  description        = "agentcore-runtime-role: invoke one Bedrock model and read or write incident items."
}

data "aws_iam_policy_document" "agentcore_runtime" {
  statement {
    sid       = "InvokeInvestigationModel"
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"]
  }

  dynamic "statement" {
    for_each = var.incidents_table_arn == "" ? [] : [var.incidents_table_arn]
    content {
      sid    = "IncidentItems"
      effect = "Allow"
      actions = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
      ]
      resources = [statement.value, "${statement.value}/index/*"]
    }
  }

  dynamic "statement" {
    for_each = var.deployments_table_arn == "" ? [] : [var.deployments_table_arn]
    content {
      sid       = "ReadDeployments"
      effect    = "Allow"
      actions   = ["dynamodb:GetItem", "dynamodb:Query"]
      resources = [statement.value, "${statement.value}/index/*"]
    }
  }
}

resource "aws_iam_role_policy" "agentcore_runtime" {
  name   = "agentcore-runtime"
  role   = aws_iam_role.agentcore_runtime.id
  policy = data.aws_iam_policy_document.agentcore_runtime.json
}

resource "aws_iam_role" "agentcore_gateway" {
  name               = "${var.project}-${var.environment}-agentcore-gateway"
  assume_role_policy = data.aws_iam_policy_document.agentcore_runtime_assume.json
  description        = "agentcore-gateway-role: read-only scopes for the four registered tools."
}

data "aws_iam_policy_document" "agentcore_gateway" {
  dynamic "statement" {
    for_each = var.incidents_table_arn == "" ? [] : [var.incidents_table_arn]
    content {
      sid       = "GetIncident"
      effect    = "Allow"
      actions   = ["dynamodb:GetItem"]
      resources = [statement.value]
    }
  }

  dynamic "statement" {
    for_each = var.deployments_table_arn == "" ? [] : [var.deployments_table_arn]
    content {
      sid       = "ReadDeployments"
      effect    = "Allow"
      actions   = ["dynamodb:GetItem", "dynamodb:Query"]
      resources = [statement.value, "${statement.value}/index/*"]
    }
  }
}

resource "aws_iam_role_policy" "agentcore_gateway" {
  name   = "agentcore-gateway-tools"
  role   = aws_iam_role.agentcore_gateway.id
  policy = data.aws_iam_policy_document.agentcore_gateway.json
}

resource "aws_iam_role" "cloudwatch_read_tool" {
  name               = "${var.project}-${var.environment}-cloudwatch-read-tool"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  description        = "cloudwatch-read-tool-role: read-only access to allowlisted demo log groups and metrics."
}
