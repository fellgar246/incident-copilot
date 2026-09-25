data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.project}-${var.environment}-knowledge-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "corpus" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_public_access_block" "corpus" {
  bucket = aws_s3_bucket.corpus.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "corpus" {
  bucket = aws_s3_bucket.corpus.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "corpus" {
  bucket = aws_s3_bucket.corpus.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "corpus" {
  bucket = aws_s3_bucket.corpus.id

  rule {
    id     = "expire-noncurrent"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

data "aws_iam_policy_document" "knowledge_tool_assume" {
  statement {
    sid     = "KnowledgeToolAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com", "bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "knowledge_tool" {
  name               = "${var.project}-${var.environment}-knowledge-tool"
  assume_role_policy = data.aws_iam_policy_document.knowledge_tool_assume.json
  description        = "knowledge-tool-role: read the corpus bucket and retrieve from a knowledge base."
}

data "aws_iam_policy_document" "knowledge_tool" {
  statement {
    sid       = "ListCorpus"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.corpus.arn]
  }

  statement {
    sid       = "ReadCorpus"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.corpus.arn}/*"]
  }

  statement {
    sid       = "RetrieveKnowledge"
    effect    = "Allow"
    actions   = ["bedrock:Retrieve"]
    resources = ["arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"]
  }
}

resource "aws_iam_role_policy" "knowledge_tool" {
  name   = "knowledge-tool"
  role   = aws_iam_role.knowledge_tool.id
  policy = data.aws_iam_policy_document.knowledge_tool.json
}
