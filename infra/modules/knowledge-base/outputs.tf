output "bucket_name" {
  description = "Private corpus bucket. Retrieval stays off when RAG_ENABLED is false."
  value       = aws_s3_bucket.corpus.bucket
}

output "bucket_arn" {
  description = "ARN of the corpus bucket."
  value       = aws_s3_bucket.corpus.arn
}

output "knowledge_tool_role_arn" {
  description = "ARN of knowledge-tool-role."
  value       = aws_iam_role.knowledge_tool.arn
}

output "knowledge_tool_role_name" {
  description = "Name of knowledge-tool-role."
  value       = aws_iam_role.knowledge_tool.name
}
