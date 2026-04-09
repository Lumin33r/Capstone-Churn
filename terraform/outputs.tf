# terraform/outputs.tf
# Values printed after terraform apply
# Share these with teammates in Slack after running apply

output "s3_bucket_name" {
  description = "Name of the S3 data bucket"
  value       = aws_s3_bucket.customer_bucket.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 data bucket"
  value       = aws_s3_bucket.customer_bucket.arn
}

output "bedrock_role_arn" {
  description = "IAM role ARN for Bedrock access — share with teammates"
  value       = aws_iam_role.bedrock_role.arn
}

output "sagemaker_invoke_role_arn" {
  description = "IAM role ARN for SageMaker invocation — share with teammates"
  value       = aws_iam_role.sagemaker_invoke_role.arn
}

output "aws_bedrock_guardrail_id" {
  description = "ID of guardrail"
  value       = aws_bedrock_guardrail.sentiment_analysis.guardrail_id
}

output "aws_bedrock_guardrail_name" {
  description = "Name of guardrail"
  value       = aws_bedrock_guardrail.sentiment_analysis.name
}