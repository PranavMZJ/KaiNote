# ------------------------------------------------------------------------------
# S3 Buckets — Data and Prompts
# Requirements: 5.4, 13.1, 15.4, 16.3
# ------------------------------------------------------------------------------

# ==============================================================================
# Data Bucket — Transcripts & Reports
# ==============================================================================

resource "aws_s3_bucket" "data" {
  bucket        = "${local.name_prefix_lower}-data"
  force_destroy = true

  tags = local.common_tags
}

# --- Versioning (enabled on data bucket) ---
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

# --- SSE-S3 encryption ---
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# --- Block all public access ---
resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Lifecycle rule: transition to Glacier after 90 days ---
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "glacier-transition"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# --- CORS for frontend origin ---
resource "aws_s3_bucket_cors_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# ==============================================================================
# Prompts Bucket — Prompt Templates & Schema Files
# ==============================================================================

resource "aws_s3_bucket" "prompts" {
  bucket        = "${local.name_prefix_lower}-prompts"
  force_destroy = true

  tags = local.common_tags
}

# --- SSE-S3 encryption ---
resource "aws_s3_bucket_server_side_encryption_configuration" "prompts" {
  bucket = aws_s3_bucket.prompts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# --- Block all public access ---
resource "aws_s3_bucket_public_access_block" "prompts" {
  bucket = aws_s3_bucket.prompts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
