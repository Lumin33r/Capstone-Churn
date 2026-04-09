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
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "s3_bucket_name" {
  description = "S3 bucket for storing transcripts and model artifacts"
  type        = string
  default     = "retention-engine-bucket"
}

variable "agent_name" {
  description = "Name of bedrock with general chat features"
  type        = string
  default     = "retention-bedrock-general-agent"
}
# Anthropic Claude
# Best for complex reasoning, analysis, and following detailed instruction
variable "agent_model" {
  description = "Foundation model ID for the agent. Change this to update models."
  type = object({
    id         = string # Bedrock model ID
    display    = string # Human-readable name for tags/logs
    model_name = string
  })
  # Model supports on‑demand invocation
  default = {
    id         = "anthropic.claude-3-haiku-20240307-v1:0" #TODO: confirm model
    display    = "Claude Haiku 3"
    model_name = "bedrock"
  }
}

variable "sentiment_endpoint_name" {
  description = "Name of the SageMaker endpoint for sentiment analysis"
  type        = string
  default     = "sentiment-analysis-endpoint"
}

variable "agent_instruction" {
  description = "The system prompt for the Bedrock agent. Defines its behavior and persona required for downstream churn analysis."
  type        = string
  default     = <<-EOT
    You are a very helpful agent created to provide general information and assistance.
    Constraints: 
      Block toxic, hateful, violent, abusive, self-harm, and PII content.
    Output: Provide general assistance.
  EOT
}

variable "idle_session_ttl" {
  description = "How long agent sessions stay open (seconds). Max 3600."
  type        = number
  default     = 600
}