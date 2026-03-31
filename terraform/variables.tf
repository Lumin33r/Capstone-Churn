# terraform/variables.tf
# All configurable values — no hardcoded values anywhere else in Terraform

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "team_name" {
  description = "Team name prefix for all resource names"
  type        = string
  default     = "retention-engine"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "staging"
}

variable "s3_bucket_name" {
  description = "S3 bucket for storing transcripts and model artifacts"
  type        = string
  default     = "retention-engine-data-staging"
}