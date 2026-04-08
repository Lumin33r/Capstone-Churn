# terraform/providers.tf
# Tells Terraform which cloud provider to use and what version

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "retention-engine-tf-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "retention-engine-tf-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
