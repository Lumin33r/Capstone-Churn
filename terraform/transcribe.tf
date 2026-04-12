# ── Amazon Transcribe Pipeline ─────────────────────────────────────────
# S3 audio upload → Lambda → Amazon Transcribe → transcript to S3
# Stretch goal: adds speech-to-text ingestion layer to the pipeline

# --- IAM Role for the Lambda function ---
resource "aws_iam_role" "transcribe_lambda_role" {
  name        = "retention-transcribe-lambda-role"
  description = "Lambda role for Transcribe pipeline"
  path        = "/retention/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "transcribe_lambda_policy" {
  name = "retention-transcribe-lambda-policy"
  role = aws_iam_role.transcribe_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "transcribe:StartTranscriptionJob",
          "transcribe:GetTranscriptionJob",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = [
          "arn:aws:s3:::retention-engine-bucket/audio/*",
          "arn:aws:s3:::retention-engine-bucket/transcripts/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
    ]
  })
}

# --- Lambda Function ---
resource "aws_lambda_function" "transcribe_pipeline" {
  function_name = "retention-transcribe-pipeline"
  role          = aws_iam_role.transcribe_lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 900 # 15 minutes — Transcribe jobs can take a few minutes

  filename         = "${path.module}/../services/transcribe-pipeline/lambda_function.zip"
  source_code_hash = filebase64sha256("${path.module}/../services/transcribe-pipeline/lambda_function.zip")

  environment {
    variables = {
      OUTPUT_BUCKET = "retention-engine-bucket"
      OUTPUT_PREFIX = "transcripts"
    }
  }
}

# --- S3 Event Notification → Lambda ---
resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.transcribe_pipeline.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::retention-engine-bucket"
}

resource "aws_s3_bucket_notification" "audio_upload_trigger" {
  bucket = "retention-engine-bucket"

  lambda_function {
    lambda_function_arn = aws_lambda_function.transcribe_pipeline.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "audio/"
    filter_suffix       = ".wav"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.transcribe_pipeline.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "audio/"
    filter_suffix       = ".mp3"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.transcribe_pipeline.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "audio/"
    filter_suffix       = ".mp4"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}
