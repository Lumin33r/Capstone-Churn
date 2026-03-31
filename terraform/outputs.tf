# terraform/outputs.tf
# Values printed after terraform apply
# Share these with teammates in Slack after running apply

output "s3_bucket_name" {
  description = "Name of the S3 data bucket"
  value       = aws_s3_bucket.data.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 data bucket"
  value       = aws_s3_bucket.data.arn
}

output "bedrock_role_arn" {
  description = "IAM role ARN for Bedrock access — share with teammates"
  value       = aws_iam_role.bedrock_role.arn
}

output "sagemaker_invoke_role_arn" {
  description = "IAM role ARN for SageMaker invocation — share with teammates"
  value       = aws_iam_role.sagemaker_invoke_role.arn
}