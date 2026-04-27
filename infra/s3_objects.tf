# ------------------------------------------------------------------------------
# S3 Objects — Prompt Templates & Schema Files
# Requirements: 7.1, 7.6, 7.7, 8.1, 8.2
# ------------------------------------------------------------------------------

resource "aws_s3_object" "prompt_template_v1" {
  bucket       = aws_s3_bucket.prompts.id
  key          = "prompts/v1/minutes_prompt.txt"
  source       = "${path.module}/../backend/prompts/v1/minutes_prompt.txt"
  content_type = "text/plain; charset=utf-8"
  etag         = filemd5("${path.module}/../backend/prompts/v1/minutes_prompt.txt")

  tags = local.common_tags
}

resource "aws_s3_object" "minutes_schema_v1" {
  bucket       = aws_s3_bucket.prompts.id
  key          = "schemas/v1/minutes_schema.json"
  source       = "${path.module}/../backend/schemas/v1/minutes_schema.json"
  content_type = "application/json"
  etag         = filemd5("${path.module}/../backend/schemas/v1/minutes_schema.json")

  tags = local.common_tags
}
