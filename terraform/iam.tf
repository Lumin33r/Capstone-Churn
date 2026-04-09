
# ── IAM Role for Bedrock access ──────────────────────────────────────
resource "aws_iam_role" "bedrock_role" {
  name = "${var.team_name}-bedrock-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = ["ec2.amazonaws.com",
        "bedrock.amazonaws.com"]
      }
      // User role will probably be the only principal with the permission to 
      // access bedrock because of trust entity (trust vs permission)
      // Could assign permission to iam role 
      // Currently all stakeholders are trusted users 
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  tags = {
    Team        = var.team_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "bedrock_invoke_policy" {
  name = "${var.team_name}-bedrock-invoke-policy"
  role = aws_iam_role.bedrock_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.agent_model.id}"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.customer_bucket.arn,
          "${aws_s3_bucket.customer_bucket.arn}/*"
        ]
      }
    ]
  })
}


# ── IAM Role for SageMaker endpoint invocation ───────────────────────
resource "aws_iam_role" "sagemaker_invoke_role" {
  name = "${var.team_name}-sagemaker-invoke-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = {
    Team        = var.team_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "sagemaker_invoke_policy" {
  name = "${var.team_name}-sagemaker-invoke-policy"
  role = aws_iam_role.sagemaker_invoke_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sagemaker:InvokeEndpoint"]
      Resource = "*"
    }]
  })
}
# ── IAM Role for SageMaker execution  ───────────────────────

resource "aws_iam_role" "sagemaker_execution_role" {
  name = "sagemaker-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "sagemaker.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Team        = var.team_name
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.sagemaker_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# ── IAM Role for SageMaker feature store  ───────────────────────

resource "aws_iam_role" "sagemaker_featurestore_role" {
  name = "sagemaker-featurestore-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "sagemaker_featurestore_policy" {
  name = "sagemaker-featurestore-policy"
  role = aws_iam_role.sagemaker_featurestore_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
       {
        Effect = "Allow"
        Action = [
          "sagemaker:AmazonSageMakerFeatureStoreAccess"
        ]
        Resource = "*"
      },
      # Allow Feature Store to write to S3 (offline store)
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject",
          "s3:GetBucketAcl"
        ]
        Resource = [
          "arn:aws:s3:::your-bucket",
          "arn:aws:s3:::your-bucket/*"
        ]
      },

      # Allow Feature Store to use Glue Data Catalog for offline store tables
      {
        Effect = "Allow"
        Action = [
          "glue:CreateTable",
          "glue:GetTable",
          "glue:GetTables",
          "glue:UpdateTable",
          "glue:CreateDatabase",
          "glue:GetDatabase",
          "glue:GetDatabases"
        ]
        Resource = "*"
      },

      # Allow Feature Store to write to the Online Store (DynamoDB)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:DescribeTable",
          "dynamodb:CreateTable"
        ]
        Resource = "arn:aws:dynamodb:*:*:table/*"
      },

      # Allow CloudWatch logging
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}


# ── IAM Role for Elastic Kubernetes Cluster  ───────────────────────

resource "aws_iam_role" "eks_cluster_role" {
  name = "eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_AmazonEKSClusterPolicy" {
  role       = aws_iam_role.eks_cluster_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "eks_node_role" {
  name = "eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_AmazonEKSWorkerNodePolicy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_node_AmazonEC2ContainerRegistryReadOnly" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_node_AmazonEKS_CNI_Policy" {
  role       = aws_iam_role.eks_node_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}