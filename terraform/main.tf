# terraform/main.tf
# Core AWS resources for the Retention Engine platform

data "aws_caller_identity" "current" {}

data "aws_vpc" "eks_vpc" {
  id = "vpc-0f8b2f344a11d2e2e"
}

data "aws_subnets" "eks_vpc" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.eks_vpc.id]
  }
}

data "aws_subnet" "default_subnets" {
  for_each = toset(data.aws_subnets.eks_vpc.ids)
  id       = each.value
}

data "aws_eks_cluster" "existing" {
  name = "eks-ezvrmopo-okl"
}

data "aws_eks_cluster_auth" "existing" {
  name = data.aws_eks_cluster.existing.name
}
