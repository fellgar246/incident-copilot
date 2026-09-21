output "api_role_arn" {
  description = "ARN of the api-role Lambda execution role."
  value       = aws_iam_role.api.arn
}

output "api_role_name" {
  description = "Name of the api-role Lambda execution role."
  value       = aws_iam_role.api.name
}

output "lambda_function_name" {
  description = "Name of the API Lambda."
  value       = aws_lambda_function.api.function_name
}

output "api_endpoint" {
  description = "HTTPS base URL of the HTTP API."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "log_group_name" {
  description = "CloudWatch log group for the API Lambda."
  value       = aws_cloudwatch_log_group.api.name
}
