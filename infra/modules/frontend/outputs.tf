output "bucket_name" {
  description = "S3 bucket that stores the static dashboard export."
  value       = aws_s3_bucket.web.bucket
}

output "distribution_id" {
  description = "CloudFront distribution that serves the dashboard."
  value       = aws_cloudfront_distribution.web.id
}

output "dashboard_url" {
  description = "HTTPS URL of the static dashboard."
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}
