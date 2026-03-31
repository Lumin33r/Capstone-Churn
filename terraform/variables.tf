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

  validation {
    condition = contain(["dev", "staging", "prod"])
    error_message = "The only allowed value are dev, staging, and prod"
  }
}

variable "s3_bucket_name" {
  description = "S3 bucket for storing transcripts and model artifacts"
  type        = string
  default     = "retention-engine-data-staging"
}

# Anthropic Claude
# Best for complex reasoning, analysis, and following detailed instruction
variable "agent_model" {
  description = "Foundation model ID for the agent. Change this to upgrade models."
  type = object({
    id      = string  # Bedrock model ID
    display = string  # Human-readable name for tags/logs
  })
  default = {
    id      = "anthropic.claude-sonnet-4-20250514-v1:0" #TODO: confirm model
    display = "Claude Sonnet 4"
  }
}

variable "agent_sentiment" {
  description = "Name of the Bedrock agent"
  type        = string
  default     = "sentiment"
}

variable "agent_instruction" {
  description = "System instruction for the agent. Defines its behavior and persona."
  type        = string
  default     = "value"
}

variable "idle_session_ttl" {
  description = "How long agent sessions stay open (seconds). Max 3600."
  type        = number
  default     = 600
}