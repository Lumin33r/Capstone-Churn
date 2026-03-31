# terraform/main.tf
# Core AWS resources for the Retention Engine platform

# ── S3 Bucket for transcripts and model data ─────────────────────────
resource "aws_s3_bucket" "data" {
  bucket = var.s3_bucket_name

  tags = {
    Name        = var.s3_bucket_name
    Environment = var.environment
    Team        = var.team_name
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ── IAM Role for Bedrock access ──────────────────────────────────────
resource "aws_iam_role" "bedrock_role" {
  name = "${var.team_name}-bedrock-role"

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