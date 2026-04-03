
# ── S3 Bucket for transcripts and model data ─────────────────────────

# Input Customer Service Data 
resource "aws_s3_bucket" "customer_bucket" {
  bucket = var.s3_bucket_name

  tags = {
    Name        = var.s3_bucket_name
    Environment = var.environment
    Team        = var.team_name
  }
}

resource "aws_s3_bucket_versioning" "customer_bucket" {
  bucket = aws_s3_bucket.customer_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "customer_bucket" {
  bucket = aws_s3_bucket.customer_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
