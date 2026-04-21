data "aws_eks_cluster" "retention_eks" {
  name = aws_eks_cluster.retention_eks.name
}

data "aws_eks_cluster_auth" "retention_eks" {
  name = aws_eks_cluster.retention_eks.name
}

resource "kubernetes_config_map_v1_data" "aws_auth" {
  metadata {
    name      = "aws-auth"
    namespace = "kube-system"
  }

  data = {
    mapRoles = yamlencode([
      {
        rolearn  = aws_iam_role.eks_node_role.arn
        username = "system:node:{{EC2PrivateDNSName}}"
        groups = [
          "system:bootstrappers",
          "system:nodes",
        ]
      },
    ])
  }

  force = true

  depends_on = [
    aws_eks_cluster.retention_eks,
    aws_eks_node_group.retention_ng,
  ]
}