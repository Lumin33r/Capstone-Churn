locals {
  # Use all default VPC subnets 
  eks_subnet_ids = data.aws_subnets.eks_vpc.ids
}

resource "aws_eks_cluster" "retention_eks" {
  name     = "eks-ezvrmopo-okl"
  role_arn = aws_iam_role.eks_cluster_role.arn
  version  = "1.29"

  vpc_config {
    subnet_ids = local.eks_subnet_ids
  }

  lifecycle {
    ignore_changes = all
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_AmazonEKSClusterPolicy
  ]
}

resource "aws_eks_node_group" "retention_ng" {
  cluster_name    = aws_eks_cluster.retention_eks.name
  node_group_name = "retention-ng"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = local.eks_subnet_ids

  scaling_config {
    desired_size = 2
    max_size     = 4
    min_size     = 1
  }

  instance_types = ["t3.medium"]

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.eks_node_AmazonEC2ContainerRegistryReadOnly,
    aws_iam_role_policy_attachment.eks_node_AmazonEKS_CNI_Policy,
    aws_eks_cluster.retention_eks
  ]
}
