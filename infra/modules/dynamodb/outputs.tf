output "incidents_table_name" {
  description = "Name of the incidents + events table."
  value       = aws_dynamodb_table.incidents.name
}

output "incidents_table_arn" {
  description = "ARN of the incidents + events table."
  value       = aws_dynamodb_table.incidents.arn
}

output "deployments_table_name" {
  description = "Name of the deployments table."
  value       = aws_dynamodb_table.deployments.name
}

output "deployments_table_arn" {
  description = "ARN of the deployments table."
  value       = aws_dynamodb_table.deployments.arn
}
