data "aws_caller_identity" "ci" {
  count = var.enable_github_oidc ? 1 : 0
}

locals {
  ci_prefix   = "${var.project}-${var.environment}"
  ci_account  = try(data.aws_caller_identity.ci[0].account_id, "")
  ci_role_arn = "arn:aws:iam::${local.ci_account}:role/${local.ci_prefix}-*"
}

# Deploy policy for ci-deploy-role.
# Resource=* appears only for APIs that reject resource-level permissions.
# Those actions are list/describe reads plus CloudFront creates, which AWS does not scope.
data "aws_iam_policy_document" "ci_deploy" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    sid    = "DenyLongLivedCredentials"
    effect = "Deny"
    actions = [
      "iam:CreateUser",
      "iam:CreateAccessKey",
      "iam:UpdateAccessKey",
      "iam:CreateLoginProfile",
    ]
    resources = ["*"]
  }

  statement {
    sid = "UnscopedReads"
    actions = [
      "sts:GetCallerIdentity",
      "ec2:DescribeAccountAttributes",
      "ec2:DescribeAvailabilityZones",
      "dynamodb:ListTables",
      "sqs:ListQueues",
      "lambda:ListFunctions",
      "lambda:ListEventSourceMappings",
      "events:ListEventBuses",
      "events:ListRules",
      "logs:DescribeLogGroups",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:ListDashboards",
      "iam:ListOpenIDConnectProviders",
      "s3:ListAllMyBuckets",
      "cloudfront:ListDistributions",
      "cloudfront:ListFunctions",
      "cloudfront:ListOriginAccessControls",
    ]
    resources = ["*"]
  }

  statement {
    sid = "AdministerProjectRoles"
    actions = [
      "iam:GetRole",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:UpdateRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:PutRolePolicy",
      "iam:GetRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:PassRole",
    ]
    resources = [local.ci_role_arn]
  }

  statement {
    sid = "GitHubOidcProvider"
    actions = [
      "iam:GetOpenIDConnectProvider",
      "iam:CreateOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider",
      "iam:TagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = [
      "arn:aws:iam::${local.ci_account}:oidc-provider/token.actions.githubusercontent.com",
    ]
  }

  statement {
    sid = "ProjectBudgets"
    actions = [
      "budgets:ViewBudget",
      "budgets:ModifyBudget",
    ]
    resources = ["arn:aws:budgets::${local.ci_account}:budget/${local.ci_prefix}-*"]
  }

  statement {
    sid = "BudgetAlertsTopic"
    actions = [
      "sns:CreateTopic",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:SetTopicAttributes",
      "sns:Subscribe",
      "sns:Unsubscribe",
      "sns:GetSubscriptionAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:TagResource",
      "sns:UntagResource",
      "sns:ListTagsForResource",
    ]
    resources = ["arn:aws:sns:${var.aws_region}:${local.ci_account}:${local.ci_prefix}-budget-alerts"]
  }

  statement {
    sid = "ProjectTables"
    actions = [
      "dynamodb:CreateTable",
      "dynamodb:DeleteTable",
      "dynamodb:DescribeTable",
      "dynamodb:UpdateTable",
      "dynamodb:TagResource",
      "dynamodb:UntagResource",
      "dynamodb:ListTagsOfResource",
      "dynamodb:UpdateTimeToLive",
      "dynamodb:DescribeTimeToLive",
      "dynamodb:DescribeContinuousBackups",
      "dynamodb:UpdateContinuousBackups",
    ]
    resources = ["arn:aws:dynamodb:${var.aws_region}:${local.ci_account}:table/${local.ci_prefix}-*"]
  }

  statement {
    sid = "ProjectQueues"
    actions = [
      "sqs:CreateQueue",
      "sqs:DeleteQueue",
      "sqs:GetQueueAttributes",
      "sqs:SetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:TagQueue",
      "sqs:UntagQueue",
      "sqs:ListQueueTags",
    ]
    resources = ["arn:aws:sqs:${var.aws_region}:${local.ci_account}:${local.ci_prefix}-*"]
  }

  statement {
    sid = "ProjectEventBus"
    actions = [
      "events:CreateEventBus",
      "events:DeleteEventBus",
      "events:DescribeEventBus",
      "events:PutRule",
      "events:DescribeRule",
      "events:DeleteRule",
      "events:PutTargets",
      "events:RemoveTargets",
      "events:ListTargetsByRule",
      "events:TagResource",
      "events:UntagResource",
      "events:ListTagsForResource",
    ]
    resources = [
      "arn:aws:events:${var.aws_region}:${local.ci_account}:event-bus/${local.ci_prefix}-*",
      "arn:aws:events:${var.aws_region}:${local.ci_account}:rule/${local.ci_prefix}-*/*",
    ]
  }

  statement {
    sid = "ProjectFunctions"
    actions = [
      "lambda:CreateFunction",
      "lambda:DeleteFunction",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:AddPermission",
      "lambda:RemovePermission",
      "lambda:GetPolicy",
      "lambda:ListVersionsByFunction",
      "lambda:TagResource",
      "lambda:UntagResource",
      "lambda:ListTags",
      "lambda:CreateEventSourceMapping",
      "lambda:GetEventSourceMapping",
      "lambda:UpdateEventSourceMapping",
      "lambda:DeleteEventSourceMapping",
      "lambda:PublishVersion",
    ]
    resources = [
      "arn:aws:lambda:${var.aws_region}:${local.ci_account}:function:${local.ci_prefix}-*",
      "arn:aws:lambda:${var.aws_region}:${local.ci_account}:event-source-mapping:*",
    ]
  }

  statement {
    sid = "HttpApi"
    actions = [
      "apigateway:GET",
      "apigateway:POST",
      "apigateway:PUT",
      "apigateway:PATCH",
      "apigateway:DELETE",
    ]
    resources = [
      "arn:aws:apigateway:${var.aws_region}::/apis",
      "arn:aws:apigateway:${var.aws_region}::/apis/*",
      "arn:aws:apigateway:${var.aws_region}::/tags/*",
      "arn:aws:apigateway:${var.aws_region}::/v2/apis",
      "arn:aws:apigateway:${var.aws_region}::/v2/apis/*",
    ]
  }

  statement {
    sid = "ProjectLogGroups"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
      "logs:ListTagsForResource",
      "logs:PutMetricFilter",
      "logs:DeleteMetricFilter",
      "logs:DescribeMetricFilters",
      "logs:ListTagsLogGroup",
      "logs:TagLogGroup",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${local.ci_account}:log-group:/${local.ci_prefix}/*",
      "arn:aws:logs:${var.aws_region}:${local.ci_account}:log-group:/aws/lambda/${local.ci_prefix}-*",
      "arn:aws:logs:${var.aws_region}:${local.ci_account}:log-group:/aws/lambda/${local.ci_prefix}-*:*",
    ]
  }

  statement {
    sid = "ProjectAlarms"
    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:PutDashboard",
      "cloudwatch:DeleteDashboards",
      "cloudwatch:GetDashboard",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "cloudwatch:ListTagsForResource",
    ]
    resources = [
      "arn:aws:cloudwatch:${var.aws_region}:${local.ci_account}:alarm:${local.ci_prefix}-*",
      "arn:aws:cloudwatch::${local.ci_account}:dashboard/${local.ci_prefix}-*",
    ]
  }

  statement {
    sid = "ProjectBuckets"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning",
      "s3:PutBucketVersioning",
      "s3:GetEncryptionConfiguration",
      "s3:PutEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:PutLifecycleConfiguration",
      "s3:GetBucketPublicAccessBlock",
      "s3:PutBucketPublicAccessBlock",
      "s3:GetBucketPolicy",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
      "s3:GetBucketTagging",
      "s3:PutBucketTagging",
      "s3:GetBucketAcl",
      "s3:GetAccelerateConfiguration",
      "s3:GetBucketCors",
      "s3:GetBucketLogging",
      "s3:GetBucketRequestPayment",
      "s3:GetBucketWebsite",
      "s3:GetReplicationConfiguration",
      "s3:GetBucketObjectLockConfiguration",
    ]
    resources = ["arn:aws:s3:::${local.ci_prefix}-*"]
  }

  statement {
    sid = "ProjectObjects"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:ListBucketVersions",
      "s3:GetObjectVersion",
    ]
    resources = ["arn:aws:s3:::${local.ci_prefix}-*/*"]
  }

  # CreateDistribution and CreateFunction do not support resource ARNs.
  statement {
    sid = "CloudFrontDistribution"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:GetDistribution",
      "cloudfront:UpdateDistribution",
      "cloudfront:DeleteDistribution",
      "cloudfront:TagResource",
      "cloudfront:UntagResource",
      "cloudfront:ListTagsForResource",
      "cloudfront:CreateOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:CreateFunction",
      "cloudfront:DescribeFunction",
      "cloudfront:GetFunction",
      "cloudfront:UpdateFunction",
      "cloudfront:DeleteFunction",
      "cloudfront:PublishFunction",
    ]
    resources = ["*"]
  }

  dynamic "statement" {
    for_each = var.terraform_state_bucket == "" ? [] : [var.terraform_state_bucket]
    content {
      sid = "RemoteStateBucket"
      actions = [
        "s3:ListBucket",
        "s3:GetBucketVersioning",
      ]
      resources = ["arn:aws:s3:::${statement.value}"]
    }
  }

  dynamic "statement" {
    for_each = var.terraform_state_bucket == "" ? [] : [var.terraform_state_bucket]
    content {
      sid = "RemoteStateObjects"
      actions = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
      ]
      resources = ["arn:aws:s3:::${statement.value}/*"]
    }
  }

  dynamic "statement" {
    for_each = var.terraform_lock_table == "" ? [] : [var.terraform_lock_table]
    content {
      sid = "RemoteStateLock"
      actions = [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
      ]
      resources = [
        "arn:aws:dynamodb:${var.aws_region}:${local.ci_account}:table/${statement.value}",
      ]
    }
  }
}

resource "aws_iam_role_policy" "ci_deploy" {
  count  = var.enable_github_oidc ? 1 : 0
  name   = "ci-deploy"
  role   = aws_iam_role.ci_deploy[0].id
  policy = data.aws_iam_policy_document.ci_deploy[0].json
}
