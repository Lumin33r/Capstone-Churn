# terraform/providers.tf
# Tells Terraform which cloud provider to use and what version

terraform {
  required_version = ">= 1.2"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.40.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.32"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.retention_eks.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.retention_eks.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.retention_eks.token
}
