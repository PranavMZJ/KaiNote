# ------------------------------------------------------------------------------
# DynamoDB — WebSocket Connections Table & Audio Buffer Table
# Requirements: 15.1, 16.1, 16.2
# ------------------------------------------------------------------------------

resource "aws_dynamodb_table" "connections" {
  name         = "${local.name_prefix}-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connectionId"

  attribute {
    name = "connectionId"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  global_secondary_index {
    name            = "userId-index"
    hash_key        = "userId"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}

# ------------------------------------------------------------------------------
# DynamoDB — Meetings Metadata Table
# Replaces S3 status.json files for meeting metadata storage.
# Partition key: userId, Sort key: meetingId (enables efficient per-user queries)
# ------------------------------------------------------------------------------

resource "aws_dynamodb_table" "meetings" {
  name         = "${local.name_prefix}-meetings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "meetingId"

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "meetingId"
    type = "S"
  }

  tags = local.common_tags
}

# ------------------------------------------------------------------------------
# DynamoDB — Audio Buffer Table
# Stores audio chunks temporarily during meeting capture.
# Partition key: meetingId, Sort key: seqNum (ensures ordering)
# TTL auto-cleanup after 1 hour.
# ------------------------------------------------------------------------------

resource "aws_dynamodb_table" "audio_buffer" {
  name         = "${local.name_prefix}-audio-buffer"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "meetingId"
  range_key    = "seqNum"

  attribute {
    name = "meetingId"
    type = "S"
  }

  attribute {
    name = "seqNum"
    type = "N"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}
