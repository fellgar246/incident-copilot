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
