
# ── IAM Role for Bedrock access ──────────────────────────────────────
resource "aws_iam_role" "bedrock_role" {
  name = "${var.team_name}-bedrock-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = {
        Service = ["ec2.amazonaws.com", "bedrock.amazonaws.com"]
      }
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

resource "aws_iam_role_policy" "bedrock_policy" {
  name = "${var.team_name}-bedrock-policy"
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
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "agent_invoke" {
  name = "bedrock-invoke"
  role = aws_iam_role.agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "bedrock:InvokeModel"
      Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.agent_model.id}"
    }]
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
